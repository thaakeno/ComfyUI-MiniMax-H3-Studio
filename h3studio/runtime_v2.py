"""Stage-isolated H3 runtime v2 for stable repeated generations.

The L4/32-GiB host profile is sensitive to dynamic model residency leaking
between H3's sequential stages. Current ComfyUI deliberately avoids unloading a
dynamic model merely to make room for another dynamic model, so H3 Studio uses
the public manager's targeted clone unload at explicit stage boundaries.

No force-full loading, direct ModelPatcher partial unload, prewarming, or global
model flush is used here.
"""

from __future__ import annotations

import inspect
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)
GIB = 1024**3
V2_RELEASE_KEY = "h3studio_v2_release_diffusion_after_sampling"
LEGACY_RELEASE_KEYS = (
    "h3studio_release_diffusion_after_sampling",
    "h3studio_sampling_residency",
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _handoffs_enabled() -> bool:
    return not _env_flag("H3STUDIO_DISABLE_STAGE_HANDOFFS")


def _loaded_size(patcher: Any) -> int:
    if patcher is None:
        return 0
    value = getattr(patcher, "loaded_size", 0)
    try:
        return max(0, int(value() if callable(value) else value))
    except Exception:
        return 0


@dataclass(frozen=True, slots=True)
class ReleaseResult:
    label: str
    mode: str
    before: int = 0
    after: int = 0
    elapsed: float = 0.0
    detail: str = ""

    def summary(self) -> str:
        text = (
            f"{self.label}={self.mode}; loaded={self.before / GIB:.2f}->{self.after / GIB:.2f}GiB; "
            f"release={self.elapsed:.3f}s"
        )
        return f"{text}; {self.detail}" if self.detail else text


def release_stage(patcher: Any, *, label: str) -> ReleaseResult:
    """Target exactly one completed stage through ComfyUI's public manager."""

    before = _loaded_size(patcher)
    if patcher is None:
        return ReleaseResult(label, "no-patcher", before=before)
    if not _handoffs_enabled():
        return ReleaseResult(label, "disabled-by-env", before=before, after=before)

    try:
        import comfy.model_management as mm
    except Exception as error:
        return ReleaseResult(label, "manager-unavailable", before=before, detail=type(error).__name__)

    unload = getattr(mm, "unload_model_and_clones", None)
    if not callable(unload):
        return ReleaseResult(label, "manager-api-missing", before=before)

    started = time.perf_counter()
    try:
        try:
            parameters = inspect.signature(unload).parameters
        except (TypeError, ValueError):
            parameters = {}

        if "unload_additional_models" in parameters:
            unload(patcher, unload_additional_models=False)
        else:
            unload(patcher)
    except Exception as error:
        result = ReleaseResult(
            label,
            "failed-nonfatal",
            before=before,
            after=_loaded_size(patcher),
            elapsed=time.perf_counter() - started,
            detail=type(error).__name__,
        )
        LOGGER.warning("[H3 Studio Runtime v2] stage release failed | %s", result.summary())
        return result

    after = _loaded_size(patcher)
    mode = "released" if before > 0 and after <= 0 else "already-offloaded" if before <= 0 else "manager-requested"
    result = ReleaseResult(label, mode, before, after, time.perf_counter() - started)
    LOGGER.info("[H3 Studio Runtime v2] stage release | %s", result.summary())
    return result


def _bundle_diffusion_patcher(bundle: Any, studio_context: Any):
    try:
        route = str(studio_context.route.selected)
        return bundle.model_for(route)
    except Exception:
        return None


def _bundle_clip_patcher(bundle: Any):
    return getattr(getattr(bundle, "clip", None), "patcher", None)


def _bundle_video_vae_patcher(bundle: Any):
    return getattr(getattr(bundle, "video_vae", None), "patcher", None)


@dataclass(slots=True)
class _ReleaseDiffusionAfterSamplingV2:
    patcher: Any

    def __call__(
        self,
        executor,
        noise,
        latent_image,
        sampler,
        sigmas,
        denoise_mask,
        callback,
        disable_pbar,
        seed,
        latent_shapes,
    ):
        try:
            return executor(
                noise,
                latent_image,
                sampler,
                sigmas,
                denoise_mask,
                callback,
                disable_pbar,
                seed,
                latent_shapes=latent_shapes,
            )
        finally:
            release_stage(self.patcher, label="diffusion-post-sample")


def _strip_legacy_sampling_wrappers(model: Any) -> None:
    try:
        import comfy.patcher_extension

        outer = comfy.patcher_extension.WrappersMP.OUTER_SAMPLE
        for key in LEGACY_RELEASE_KEYS:
            model.remove_wrappers_with_key(outer, key)

        prepare = getattr(comfy.patcher_extension.WrappersMP, "PREPARE_SAMPLING", None)
        if prepare is not None:
            model.remove_wrappers_with_key(prepare, "h3studio_sampling_residency")
    except Exception as error:
        LOGGER.debug("[H3 Studio Runtime v2] legacy wrapper cleanup skipped: %s", error)


def _attach_release_wrapper(model: Any) -> str:
    if not _handoffs_enabled():
        return "disabled-by-env"
    try:
        import comfy.patcher_extension

        wrapper_type = comfy.patcher_extension.WrappersMP.OUTER_SAMPLE
        _strip_legacy_sampling_wrappers(model)
        model.remove_wrappers_with_key(wrapper_type, V2_RELEASE_KEY)
        model.add_wrapper_with_key(
            wrapper_type,
            V2_RELEASE_KEY,
            _ReleaseDiffusionAfterSamplingV2(model),
        )
        return "manager-targeted-v2"
    except Exception as error:
        LOGGER.warning("[H3 Studio Runtime v2] could not attach diffusion release: %s", error)
        return "unavailable"


def recovered_node_classes(base_condition, base_sampling, base_decode):
    class H3StudioConditionV2(base_condition):
        """Clean previous stage state before conditioning and before sampling."""

        def condition(self, h3_bundle, studio_context):
            # A previous generation can leave diffusion/VAE/CLIP objects in
            # DynamicVRAM's loaded set. Clear those exact patchers before the
            # next stage starts; cached conditioning tensors stay untouched.
            pre = (
                release_stage(_bundle_diffusion_patcher(h3_bundle, studio_context), label="pre-condition-diffusion"),
                release_stage(_bundle_video_vae_patcher(h3_bundle), label="pre-condition-vae"),
                release_stage(_bundle_clip_patcher(h3_bundle), label="pre-condition-clip"),
            )
            started = time.perf_counter()
            result = super().condition(h3_bundle, studio_context)
            post_clip = release_stage(_bundle_clip_patcher(h3_bundle), label="post-condition-clip")

            final_vae = result[4] if isinstance(result, tuple) and len(result) > 4 else getattr(h3_bundle, "video_vae", None)
            post_vae = release_stage(getattr(final_vae, "patcher", None), label="post-condition-vae")
            LOGGER.info(
                "[H3 Studio Runtime v2] conditioning boundary | %.3fs | pre=[%s] | post=[%s | %s]",
                time.perf_counter() - started,
                " | ".join(item.summary() for item in pre),
                post_clip.summary(),
                post_vae.summary(),
            )
            return result

    class H3StudioSamplingV2(base_sampling):
        """Keep LightX/custom-LoRA behavior but own only the stage boundary."""

        def build(self, model, studio_context):
            built_model, sampler, sigmas, info = super().build(model, studio_context)
            _strip_legacy_sampling_wrappers(built_model)
            handoff = _attach_release_wrapper(built_model)
            info = f"{info} | runtime_v2=stage-isolated | sampling_handoff={handoff}"
            LOGGER.info("[H3 Studio Runtime v2] sampling boundary armed | %s", handoff)
            return built_model, sampler, sigmas, info

    class H3StudioDecodeV2(base_decode):
        """Use the native H3 VAE path, then remove final VAE residency."""

        def decode(self, samples, vae):
            first_stage = getattr(vae, "first_stage_model", None)
            chunked = bool(getattr(first_stage, "comfy_has_chunked_io", False))
            started = time.perf_counter()
            try:
                result = super().decode(samples, vae)
            finally:
                release = release_stage(getattr(vae, "patcher", None), label="final-vae-post-decode")
                LOGGER.info(
                    "[H3 Studio Runtime v2] decode boundary | path=%s | %.3fs | %s",
                    "native-chunked" if chunked else "native-legacy",
                    time.perf_counter() - started,
                    release.summary(),
                )
            return result

    H3StudioConditionV2.__name__ = "H3StudioConditionV2"
    H3StudioSamplingV2.__name__ = "H3StudioSamplingV2"
    H3StudioDecodeV2.__name__ = "H3StudioDecodeV2"
    return H3StudioConditionV2, H3StudioSamplingV2, H3StudioDecodeV2
