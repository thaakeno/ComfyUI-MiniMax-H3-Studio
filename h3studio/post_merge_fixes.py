"""Small post-merge fixes for guided T2I conditioning, roles, and previews."""

from __future__ import annotations

import logging
import time
from contextlib import suppress

LOGGER = logging.getLogger(__name__)
_MARKER = "__h3studio_post_merge_v21__"
_PREVIEW_MARKER = "__h3studio_native_preview_decode_v25__"
_REALTIME_PREVIEW_DECODE_EDGE = 1280
_MIN_REALTIME_PREVIEW_DECODE_EDGE = 1024


def _install_single_reference_semantic_resize() -> None:
    """Apply the existing 512px semantic-copy optimization to one-reference T2I too."""

    from .consolidated_integrity_fix import _semantic_copy
    from .constants import MODE_TEXT_TO_IMAGE
    from .nodes.director import H3StudioCondition

    current = H3StudioCondition.condition
    if bool(getattr(current, _MARKER, False)):
        return
    previous = current

    def condition(self, h3_bundle, studio_context):
        refs = tuple(getattr(studio_context, "images", ()) or ())
        mode = str(getattr(getattr(studio_context, "compile_result", None), "resolved_mode", ""))
        clip = getattr(h3_bundle, "clip", None)
        tokenize = getattr(clip, "tokenize", None)

        # The consolidated v18 wrapper already handles 2+ references. Only fill
        # the accidental one-reference gap here, leaving FL2VA source/VAE pixels untouched.
        if mode != MODE_TEXT_TO_IMAGE or len(refs) != 1 or not callable(tokenize):
            return previous(self, h3_bundle, studio_context)

        def semantic_tokenize(text, *args, **kwargs):
            images = kwargs.get("images")
            if isinstance(images, (list, tuple)) and images:
                kwargs = dict(kwargs)
                kwargs["images"] = [_semantic_copy(image, 512) for image in images]
                LOGGER.info(
                    "[H3 Studio] Guided T2I semantic ref capped at 512px for 32B conditioning; full-res FL2VA keyframe preserved"
                )
            return tokenize(text, *args, **kwargs)

        try:
            clip.tokenize = semantic_tokenize
        except Exception:
            return previous(self, h3_bundle, studio_context)
        try:
            return previous(self, h3_bundle, studio_context)
        finally:
            with suppress(Exception):
                clip.tokenize = tokenize

    setattr(condition, _MARKER, True)
    H3StudioCondition.condition = condition


def _install_prompt_aware_auto_roles() -> None:
    """Let explicit @Image prompt language outrank a coarse VLM content label."""

    from .nodes import director as director_module
    from .prompting import comfy_analyzer
    from .references import infer_roles_from_prompt

    current = comfy_analyzer.analyze_references
    if bool(getattr(current, _MARKER, False)):
        return
    previous = current

    def analyze_references(clip, prompt, references, images, **kwargs):
        analyzed, enhanced, note = previous(clip, prompt, references, images, **kwargs)
        corrected = infer_roles_from_prompt(prompt, analyzed)
        changes = [
            f"@Image{before.ordinal}:{before.effective_role}->{after.effective_role}"
            for before, after in zip(analyzed, corrected, strict=False)
            if before.effective_role != after.effective_role
        ]
        if changes:
            LOGGER.info("[H3 Studio - Vision] Prompt-aware auto roles | %s", ", ".join(changes))
            note = f"{note} Prompt-aware role correction: {', '.join(changes)}."
        return corrected, enhanced, note

    setattr(analyze_references, _MARKER, True)
    comfy_analyzer.analyze_references = analyze_references

    # Director imports the function directly, so update that live binding too.
    if getattr(director_module, "analyze_references", None) is previous:
        director_module.analyze_references = analyze_references


def _rgb_preview_limit(torch, image, max_resolution: int):
    """Resize decoded RGB pixels to the requested display size."""

    height, width = int(image.shape[-2]), int(image.shape[-1])
    longest = max(height, width)
    if longest <= max_resolution:
        return image
    scale = float(max_resolution) / float(longest)
    target_h = max(1, round(height * scale))
    target_w = max(1, round(width * scale))
    return torch.nn.functional.interpolate(image, size=(target_h, target_w), mode="area")


def _latent_for_realtime_preview(torch, latent, max_resolution: int):
    """Keep TAEH3 close to the sampler without returning to destructive 768px latent decoding.

    Full native 2MP decoding is visually clean but too expensive on CPU: the
    preview worker can take longer than one H3 denoising step and then displays
    stale frames. Decode a moderately reduced latent instead. The 1280px ceiling
    keeps far more latent spatial structure than the old direct-768 path while
    cutting convolution work enough for the one-slot latest-frame queue to keep up.
    """

    output_h = int(latent.shape[-2]) * 16
    output_w = int(latent.shape[-1]) * 16
    longest = max(output_h, output_w)

    requested = max(_MIN_REALTIME_PREVIEW_DECODE_EDGE, int(max_resolution) * 5 // 3)
    decode_edge = min(_REALTIME_PREVIEW_DECODE_EDGE, requested)
    if longest <= decode_edge:
        return latent, "native-latent"

    scale = float(decode_edge) / float(longest)
    target_h = max(2, round(int(latent.shape[-2]) * scale))
    target_w = max(2, round(int(latent.shape[-1]) * scale))
    reduced = torch.nn.functional.interpolate(latent, size=(target_h, target_w), mode="area")

    # Preserve each latent channel's first/second moments. The previous 768px
    # resize collapsed those distributions and produced severe doubled/smeared
    # structures; this gentler reduction plus moment restoration avoids that path.
    src_mean = latent.mean(dim=(-2, -1), keepdim=True)
    src_std = latent.std(dim=(-2, -1), keepdim=True, unbiased=False).clamp_min(1e-6)
    dst_mean = reduced.mean(dim=(-2, -1), keepdim=True)
    dst_std = reduced.std(dim=(-2, -1), keepdim=True, unbiased=False).clamp_min(1e-6)
    reduced = (reduced - dst_mean) * (src_std / dst_std).clamp(0.25, 4.0) + src_mean
    return reduced, f"realtime-latent-{decode_edge}"


def _install_preview_decode_quality() -> None:
    """Use a quality-preserving realtime TAEH3 decode budget, then resize in RGB."""

    from .nodes import preview as preview_module

    current = preview_module._PreviewWrapper._send
    if bool(getattr(current, _PREVIEW_MARKER, False)):
        return

    def _send(self, job):
        if job.run_id != self.active_run_id:
            return
        import torch

        started = time.perf_counter()
        latent, decode_mode = _latent_for_realtime_preview(torch, job.latent, self.max_resolution)
        decoder = self._load(torch)

        # channels_last lets oneDNN/MKLDNN use its preferred CPU convolution
        # layout on common x86 hosts. It is a no-op fallback if unsupported.
        try:
            if not bool(getattr(self, "_h3s_channels_last", False)):
                self.decoder = decoder.to(memory_format=torch.channels_last)
                decoder = self.decoder
                self._h3s_channels_last = True
            latent = latent.contiguous(memory_format=torch.channels_last)
        except Exception:
            pass

        with torch.inference_mode():
            image = decoder(latent).clamp(0, 1)
            image = _rgb_preview_limit(torch, image, self.max_resolution).clamp(0, 1)
        if job.run_id != self.active_run_id:
            return

        data_url, width, height = preview_module._jpeg_data_url(torch, image, self.jpeg_quality)
        from server import PromptServer

        server = PromptServer.instance
        server.send_sync(
            "h3studio-preview",
            {
                "node_id": self.node_id,
                "image": data_url,
                "step": job.step + 1,
                "total": job.total_steps,
                "width": width,
                "height": height,
                "run_id": job.run_id,
                "elapsed_seconds": job.elapsed_seconds,
                "average_step_seconds": job.average_step_seconds,
                "eta_seconds": max(0.0, job.average_step_seconds * (job.total_steps - job.step - 1)),
                "preview_mode": f"{decode_mode}->rgb-{self.max_resolution}",
            },
            server.client_id,
        )
        if not self.first_frame_reported:
            self.first_frame_reported = True
            LOGGER.info(
                "[H3 Studio] TAEH3 live preview active | first frame %dx%d | cpu %.3fs | decode=%s->rgb-%d",
                width,
                height,
                time.perf_counter() - started,
                decode_mode,
                self.max_resolution,
            )

    setattr(_send, _PREVIEW_MARKER, True)
    preview_module._PreviewWrapper._send = _send


def install() -> None:
    _install_single_reference_semantic_resize()
    _install_prompt_aware_auto_roles()
    _install_preview_decode_quality()
    LOGGER.info("[H3 Studio] Post-merge v21 conditioning/role/preview fixes installed")


__all__ = ["install"]
