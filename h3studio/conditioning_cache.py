"""Staged H3 conditioning cache and DynamicVRAM handoff helpers.

The Studio's visible Condition node used to cache one monolithic tuple keyed by
prompt + canvas + references.  A prompt edit therefore threw away reusable VAE
and latent work, then asked ComfyUI to load the 32B text encoder while the H3
transformer from the previous sample was still dynamically resident.

This module keeps those concerns independent.  It intentionally does *not*
skip text encoding for a changed prompt; it makes room for that encode, reuses
only genuinely prompt-independent work, and releases the encoder's device
residency again before sampling while leaving ComfyUI's host-side staged model
state intact.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Hashable

LOGGER = logging.getLogger(__name__)


class _LRUCache:
    def __init__(self, max_entries: int):
        self.max_entries = max(1, int(max_entries))
        self._values: OrderedDict[Hashable, Any] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: Hashable):
        with self._lock:
            if key not in self._values:
                return None
            value = self._values.pop(key)
            self._values[key] = value
            return value

    def put(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._values.pop(key, None)
            self._values[key] = value
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


# Keep these deliberately small.  The prompt cache holds conditioning tensors;
# the reference cache holds VAE latents, not duplicate full-resolution pixels.
_PROMPT_CACHE = _LRUCache(8)
_LATENT_CACHE = _LRUCache(4)
_REFERENCE_VAE_CACHE = _LRUCache(12)
_SOURCE_VAE_CACHE = _LRUCache(4)
_PREVIEW_CACHE = _LRUCache(4)


def clear_conditioning_caches() -> None:
    """Clear process caches. Primarily useful for tests and diagnostics."""

    for cache in (_PROMPT_CACHE, _LATENT_CACHE, _REFERENCE_VAE_CACHE, _SOURCE_VAE_CACHE, _PREVIEW_CACHE):
        cache.clear()


def _tensor_identity(image: Any, reference: Any = None) -> tuple[Any, ...]:
    shape = tuple(getattr(image, "shape", ()))
    dtype = str(getattr(image, "dtype", ""))
    fingerprint = str(getattr(reference, "fingerprint", "") or "").strip() if reference is not None else ""
    if fingerprint:
        return ("fingerprint", fingerprint, shape, dtype)

    # Never trust a filename/storage_name alone: the bytes behind a path can be
    # replaced while the name stays unchanged.  Comfy tensors expose a storage
    # pointer plus _version, which changes when the tensor is mutated in place.
    data_ptr = getattr(image, "data_ptr", None)
    pointer = data_ptr() if callable(data_ptr) else id(image)
    return ("tensor", pointer, int(getattr(image, "_version", 0)), shape, dtype)


def image_cache_key(studio_context: Any, images: tuple[Any, ...] | None = None) -> tuple[Any, ...]:
    images = tuple(studio_context.images if images is None else images)
    references = tuple(getattr(studio_context.state, "references", ()))
    values = []
    for index, image in enumerate(images):
        reference = references[index] if index < len(references) else None
        values.append(_tensor_identity(image, reference))
    return tuple(values)


def _patcher(value: Any):
    if value is None:
        return None
    if callable(getattr(value, "is_dynamic", None)) and callable(getattr(value, "partially_unload", None)):
        return value
    candidate = getattr(value, "patcher", None)
    if callable(getattr(candidate, "is_dynamic", None)) and callable(getattr(candidate, "partially_unload", None)):
        return candidate
    return None


@dataclass(frozen=True, slots=True)
class ResidencyRelease:
    label: str
    state: str
    freed_bytes: int = 0

    @property
    def summary(self) -> str:
        if self.freed_bytes > 0:
            return f"{self.label}:{self.state}({self.freed_bytes / (1024 ** 2):.0f}MiB)"
        return f"{self.label}:{self.state}"


def release_dynamic_device_residency(value: Any, label: str) -> ResidencyRelease:
    """Free only DynamicVRAM device residency, preserving staged host weights.

    ModelPatcherDynamic.partially_unload(None, ...) releases VBAR/device pages
    without doing a full unpatch that would also discard its pinned host state.
    Older/non-dynamic patchers are left to ComfyUI's normal model manager.
    """

    patcher = _patcher(value)
    if patcher is None:
        return ResidencyRelease(label, "managed")
    try:
        if not bool(patcher.is_dynamic()):
            return ResidencyRelease(label, "managed")
    except Exception:
        return ResidencyRelease(label, "managed")

    try:
        before = int(patcher.loaded_size()) if callable(getattr(patcher, "loaded_size", None)) else 0
    except Exception:
        before = 0
    try:
        freed = patcher.partially_unload(None, 1e32)
        freed = int(freed or 0)
        try:
            after = int(patcher.loaded_size()) if callable(getattr(patcher, "loaded_size", None)) else 0
        except Exception:
            after = 0
        freed = max(freed, max(0, before - after))
        return ResidencyRelease(label, "released", freed)
    except Exception as exc:
        LOGGER.debug("[H3 Studio] Could not release %s DynamicVRAM residency: %s", label, exc)
        return ResidencyRelease(label, "managed")


def _soft_empty_cache() -> None:
    try:
        import comfy.model_management

        comfy.model_management.soft_empty_cache()
    except Exception:
        pass


def prepare_text_encoder_workspace(bundle: Any) -> tuple[ResidencyRelease, ...]:
    """Make VRAM room for Qwen without destroying warm host-side model state."""

    candidates = (
        (getattr(bundle, "_model", None), "h3_transformer"),
        (getattr(bundle, "video_vae", None), "video_vae"),
        (getattr(bundle, "image_vae", None), "image_vae"),
        (getattr(bundle, "analyzer_clip", None), "image_analyzer"),
        (getattr(bundle, "prompt_writer_clip", None), "prompt_writer"),
    )
    seen: set[int] = set()
    releases = []
    for value, label in candidates:
        patcher = _patcher(value)
        if patcher is None or id(patcher) in seen:
            continue
        seen.add(id(patcher))
        releases.append(release_dynamic_device_residency(patcher, label))
    if releases:
        _soft_empty_cache()
    return tuple(releases)


def release_text_encoder_workspace(clip: Any) -> ResidencyRelease:
    """Give the sampler the encoder's GPU pages back after a prompt encode."""

    result = release_dynamic_device_residency(clip, "text_encoder")
    if result.state == "released":
        _soft_empty_cache()
    return result


def _selected_model_key(bundle: Any, route: str) -> str:
    selected = getattr(bundle, "selected_name", None)
    if callable(selected):
        try:
            return str(selected(route))
        except Exception:
            pass
    return str(getattr(bundle, "ref2va_name" if route == "ref2va" else "fl2va_name", ""))


def _clip_key(bundle: Any) -> tuple[Any, ...]:
    clip = bundle.clip
    return (str(getattr(bundle, "clip_name", "")), id(getattr(clip, "patcher", clip)))


def _vae_key(bundle: Any) -> tuple[Any, ...]:
    vae = bundle.video_vae
    return (str(getattr(bundle, "video_vae_name", "")), id(getattr(vae, "patcher", vae)))


def _reference_target_size(image: Any, reference_size: str, width: int, height: int) -> tuple[int, int]:
    from .nodes.image_runtime import CANVAS_MULTIPLE, REF_IMAGE_SHORT_EDGE

    h, w = int(image.shape[1]), int(image.shape[2])
    if reference_size == "max_identity_2048":
        scale = min(1.0, REF_IMAGE_SHORT_EDGE / min(w, h))
    else:
        scale = min(1.0, math.sqrt((width * height) / max(1, w * h)))
    tw = max(CANVAS_MULTIPLE, round(w * scale / CANVAS_MULTIPLE) * CANVAS_MULTIPLE)
    th = max(CANVAS_MULTIPLE, round(h * scale / CANVAS_MULTIPLE) * CANVAS_MULTIPLE)
    return tw, th


@dataclass(frozen=True, slots=True)
class ConditioningStages:
    conditioning: Any
    latent: Any
    fitted_source: Any
    requested_frames: int
    runtime_info: str
    diagnostics: str


def _latent_stage(runtime_mode: str, width: int, height: int, frame_preset: str):
    from .nodes.image_runtime import _empty_h3_av_latent, _resolve_frame_count

    key = (runtime_mode, int(width), int(height), str(frame_preset))
    cached = _LATENT_CACHE.get(key)
    if cached is not None:
        return (*cached, "HIT")

    internal_frames = _resolve_frame_count(frame_preset)
    dynamic_edit_selection = runtime_mode == "image_to_image (FL2VA)" and internal_frames == 20
    output_strategy = "first_stable_edit" if dynamic_edit_selection else "fixed"
    latent, requested_frames, natural_frames = _empty_h3_av_latent(
        width,
        height,
        internal_frames,
        output_frames=internal_frames,
        output_frame_index=0,
        output_strategy=output_strategy,
    )
    value = (latent, requested_frames, natural_frames, internal_frames, output_strategy)
    _LATENT_CACHE.put(key, value)
    return (*value, "MISS")


def _preview_black(width: int, height: int):
    key = (int(width), int(height))
    cached = _PREVIEW_CACHE.get(key)
    if cached is not None:
        return cached
    import torch

    value = torch.zeros((1, int(height), int(width), 3), dtype=torch.float32)
    _PREVIEW_CACHE.put(key, value)
    return value


def _encode_prompt(bundle: Any, key: Hashable, build_tokens) -> tuple[Any, str, float, str]:
    cached = _PROMPT_CACHE.get(key)
    if cached is not None:
        return cached, "HIT", 0.0, "warm-cache"

    releases = prepare_text_encoder_workspace(bundle)
    residency_before = ",".join(item.summary for item in releases) if releases else "no-competing-dynamic-model"
    started = time.perf_counter()
    tokens = build_tokens()
    conditioning = bundle.clip.encode_from_tokens_scheduled(tokens)
    seconds = time.perf_counter() - started
    encoder_release = release_text_encoder_workspace(bundle.clip)
    _PROMPT_CACHE.put(key, conditioning)
    residency = f"before={residency_before}; after={encoder_release.summary}"
    return conditioning, "MISS", seconds, residency


def _source_stage(bundle: Any, image: Any, image_id: Hashable, width: int, height: int, source_fit: str):
    from .nodes.image_runtime import _resize_image

    key = (_vae_key(bundle), image_id, int(width), int(height), str(source_fit))
    cached = _SOURCE_VAE_CACHE.get(key)
    if cached is not None:
        return (*cached, "HIT")
    fitted = _resize_image(image[:1], width, height, source_fit)
    latent = bundle.video_vae.encode(fitted)
    value = (fitted, latent)
    _SOURCE_VAE_CACHE.put(key, value)
    return (*value, "MISS")


def _reference_vae_stage(
    bundle: Any,
    image: Any,
    image_id: Hashable,
    width: int,
    height: int,
    reference_size: str,
    resized_image: Any | None = None,
):
    from .nodes.image_runtime import _reference_resize

    tw, th = _reference_target_size(image, reference_size, width, height)
    dimension_key = (tw, th) if reference_size == "max_identity_2048" else (tw, th, int(width), int(height))
    key = (_vae_key(bundle), image_id, str(reference_size), dimension_key)
    cached = _REFERENCE_VAE_CACHE.get(key)
    if cached is not None:
        return (*cached, "HIT")
    if resized_image is None:
        resized_image, tw, th = _reference_resize(image, width, height, reference_size)
    latent = bundle.video_vae.encode(resized_image)
    value = (latent, tw, th)
    _REFERENCE_VAE_CACHE.put(key, value)
    return (*value, "MISS")


def run_conditioning_pipeline(
    bundle: Any,
    studio_context: Any,
    *,
    route: str,
    runtime_mode: str,
    used_images: tuple[Any, ...],
    frame_preset: str,
    source_fit: str = "crop_center",
    reference_size: str = "max_identity_2048",
) -> ConditioningStages:
    """Build H3 conditioning using independent prompt/reference/latent stages."""

    import node_helpers

    from .nodes.image_runtime import _prompt_warning, _reference_resize, _resize_image

    width, height = int(studio_context.width), int(studio_context.height)
    prompt = str(studio_context.prompt)
    model_key = _selected_model_key(bundle, route)
    clip_key = _clip_key(bundle)
    image_ids = image_cache_key(studio_context, used_images)

    latent, requested_frames, natural_frames, internal_frames, output_strategy, latent_state = _latent_stage(
        runtime_mode, width, height, frame_preset
    )
    fitted_source = _preview_black(width, height)
    reference_state = "N/A"

    prompt_key_base = (model_key, route, runtime_mode, clip_key, prompt)
    text_started = time.perf_counter()

    if runtime_mode == "text_to_image (FL2VA)":
        prompt_key = (*prompt_key_base, "text-only")
        conditioning, text_state, text_seconds, residency = _encode_prompt(
            bundle,
            prompt_key,
            lambda: bundle.clip.tokenize(prompt, images=[]),
        )
        checkpoint_note = "Use an FL2VA checkpoint."

    elif runtime_mode == "image_to_image (FL2VA)":
        if not used_images:
            raise ValueError("Image to Image mode requires source_image.")
        source_id = image_ids[0]
        # Make room before the source VAE too; on a warm run the previous H3
        # transformer can otherwise crowd both VAE and Qwen.
        releases = prepare_text_encoder_workspace(bundle)
        fitted_source, keyframe_latent, source_state = _source_stage(
            bundle, used_images[0], source_id, width, height, source_fit
        )
        reference_state = f"source_vae:{source_state}"
        prompt_key = (*prompt_key_base, "i2i", source_id, width, height, source_fit)
        conditioning, text_state, text_seconds, residency = _encode_prompt(
            bundle,
            prompt_key,
            lambda: bundle.clip.tokenize(prompt, images=[fitted_source]),
        )
        if releases:
            residency = f"pre_source={','.join(item.summary for item in releases)}; {residency}"
        conditioning = node_helpers.conditioning_set_values(
            conditioning,
            {
                "minimax_keyframes": [{"resolved_frame_index": 0, "latent": keyframe_latent}],
                "minimax_frame_count": natural_frames,
            },
        )
        checkpoint_note = "Use an FL2VA checkpoint; frame 0 is the exact source anchor."

    else:
        if not used_images:
            raise ValueError("Reference Edit mode requires source_image as <Picture 1>.")
        releases = prepare_text_encoder_workspace(bundle)
        # Fitted source is only a UI/debug preview; it is deliberately separate
        # from the REF2VA identity-size conditioning cache.
        preview_key = ("ref-preview", image_ids[0], width, height, source_fit)
        preview = _PREVIEW_CACHE.get(preview_key)
        if preview is None:
            preview = _resize_image(used_images[0][:1], width, height, source_fit)
            _PREVIEW_CACHE.put(preview_key, preview)
        fitted_source = preview

        ref_signatures = []
        for image, image_id in zip(used_images, image_ids, strict=False):
            tw, th = _reference_target_size(image, reference_size, width, height)
            ref_signatures.append((image_id, tw, th))
        prompt_key = (*prompt_key_base, "ref2va", tuple(ref_signatures), reference_size)

        cached_prompt = _PROMPT_CACHE.get(prompt_key)
        resized_refs = []
        if cached_prompt is None:
            for image in used_images:
                resized, _tw, _th = _reference_resize(image, width, height, reference_size)
                resized_refs.append(resized)
            residency_before = ",".join(item.summary for item in releases) if releases else "no-competing-dynamic-model"
            started = time.perf_counter()
            tokens = bundle.clip.tokenize(
                prompt,
                minimax_ref_items=[{"type": "image", "data": image} for image in resized_refs],
            )
            conditioning = bundle.clip.encode_from_tokens_scheduled(tokens)
            text_seconds = time.perf_counter() - started
            encoder_release = release_text_encoder_workspace(bundle.clip)
            residency = f"before={residency_before}; after={encoder_release.summary}"
            text_state = "MISS"
            _PROMPT_CACHE.put(prompt_key, conditioning)
        else:
            conditioning = cached_prompt
            text_seconds = 0.0
            text_state = "HIT"
            residency = "warm-cache"

        ref_blocks = []
        ref_states = []
        ref_sizes = []
        for index, (image, image_id) in enumerate(zip(used_images, image_ids, strict=False)):
            resized = resized_refs[index] if index < len(resized_refs) else None
            latent_ref, tw, th, state = _reference_vae_stage(
                bundle,
                image,
                image_id,
                width,
                height,
                reference_size,
                resized_image=resized,
            )
            ref_blocks.append({"kind": "image", "latent_h": th // 16, "latent_w": tw // 16, "latent": latent_ref})
            ref_states.append(state)
            ref_sizes.append(f"{tw}x{th}")
        hits = sum(state == "HIT" for state in ref_states)
        reference_state = f"reference_vae:{hits}/{len(ref_states)} HIT"
        conditioning = node_helpers.conditioning_set_values(
            conditioning,
            {"minimax_refs": ref_blocks, "minimax_frame_count": natural_frames},
        )
        checkpoint_note = (
            f"Use a REF2VA checkpoint; {len(used_images)} ordered reference image(s) encoded as "
            f"{', '.join(ref_sizes)} and exposed as <Picture 1> through <Picture {len(used_images)}>。"
        )

    total_text_seconds = max(text_seconds, time.perf_counter() - text_started if text_state == "MISS" else 0.0)
    if natural_frames > 362:
        trained_note = "beyond the documented 124-362-frame training range"
    elif natural_frames >= 124:
        trained_note = "inside the documented 124-362-frame training range"
    else:
        trained_note = "short experimental temporal packet chosen to reduce image-mode compute"
    decode_note = (
        f"exact {requested_frames}-frame batch"
        if requested_frames == natural_frames
        else f"temporal latent naturally decodes {natural_frames} frames; H3 Exact Frame Decode keeps the requested {requested_frames}"
    )
    runtime_info = (
        f"Mode: {runtime_mode} | temporal profile: {internal_frames} frames | canvas {width}×{height} | "
        f"internal packet {natural_frames} frames | decoded profile {requested_frames} | {decode_note} | "
        f"{trained_note}. {checkpoint_note} Decode only the video latent; the audio VAE is unnecessary for image output. "
        f"Preferred output strategy: {output_strategy}; Single Image Output receives the full decoded profile and normally "
        f"emits one selected frame unless emit_candidate_batch is enabled.{_prompt_warning(prompt)}"
    )
    diagnostics = (
        f"text_conditioning={text_state} ({text_seconds:.3f}s) | "
        f"reference_conditioning={reference_state} | latent_prepare={latent_state} | "
        f"text_encoder_residency={residency}"
    )
    LOGGER.info("[H3 Studio] Conditioning stages\n  %s", diagnostics)
    return ConditioningStages(
        conditioning=conditioning,
        latent=latent,
        fitted_source=fitted_source,
        requested_frames=requested_frames,
        runtime_info=runtime_info,
        diagnostics=diagnostics,
    )
