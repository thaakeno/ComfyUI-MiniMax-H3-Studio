"""Independent, bounded caches for MiniMax H3 conditioning stages."""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Any

from .performance import prewarm_vae, text_encoder_residency

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


_PROMPT_CACHE = _LRUCache(8)
_LATENT_CACHE = _LRUCache(4)
_REFERENCE_VAE_CACHE = _LRUCache(12)
_SOURCE_VAE_CACHE = _LRUCache(4)
_PREVIEW_CACHE = _LRUCache(4)


def clear_conditioning_caches() -> None:
    for cache in (_PROMPT_CACHE, _LATENT_CACHE, _REFERENCE_VAE_CACHE, _SOURCE_VAE_CACHE, _PREVIEW_CACHE):
        cache.clear()


def _tensor_identity(image: Any, reference: Any = None) -> tuple[Any, ...]:
    shape = tuple(getattr(image, "shape", ()))
    dtype = str(getattr(image, "dtype", ""))
    fingerprint = str(getattr(reference, "fingerprint", "") or "").strip() if reference is not None else ""
    if fingerprint:
        return ("fingerprint", fingerprint, shape, dtype)
    data_ptr = getattr(image, "data_ptr", None)
    pointer = data_ptr() if callable(data_ptr) else id(image)
    return ("tensor", pointer, int(getattr(image, "_version", 0)), shape, dtype)


def image_cache_key(studio_context: Any, images: tuple[Any, ...] | None = None) -> tuple[Any, ...]:
    images = tuple(studio_context.images if images is None else images)
    references = tuple(getattr(studio_context.state, "references", ()))
    return tuple(
        _tensor_identity(image, references[index] if index < len(references) else None)
        for index, image in enumerate(images)
    )


def _selected_model_key(bundle: Any, route: str) -> str:
    selected = getattr(bundle, "selected_name", None)
    if callable(selected):
        return str(selected(route))
    return str(getattr(bundle, "ref2va_name" if route == "ref2va" else "fl2va_name", ""))


def _clip_key(bundle: Any) -> tuple[Any, ...]:
    clip = bundle.clip
    return str(getattr(bundle, "clip_name", "")), id(getattr(clip, "patcher", clip))


def _vae_key(bundle: Any) -> tuple[Any, ...]:
    vae = bundle.video_vae
    return str(getattr(bundle, "video_vae_name", "")), id(getattr(vae, "patcher", vae))


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

    key = runtime_mode, int(width), int(height), str(frame_preset)
    cached = _LATENT_CACHE.get(key)
    if cached is not None:
        return (*cached, "HIT")
    internal_frames = _resolve_frame_count(frame_preset)
    output_strategy = "first_stable_edit" if runtime_mode == "image_to_image (FL2VA)" and internal_frames == 20 else "fixed"
    latent, requested_frames, natural_frames = _empty_h3_av_latent(
        width,
        height,
        internal_frames,
        output_frames=internal_frames,
        output_frame_index=0,
        output_strategy=output_strategy,
    )
    value = latent, requested_frames, natural_frames, internal_frames, output_strategy
    _LATENT_CACHE.put(key, value)
    return (*value, "MISS")


def _preview_black(width: int, height: int):
    key = int(width), int(height)
    cached = _PREVIEW_CACHE.get(key)
    if cached is not None:
        return cached
    import torch

    value = torch.zeros((1, int(height), int(width), 3), dtype=torch.float32)
    _PREVIEW_CACHE.put(key, value)
    return value


def _encode_prompt(bundle: Any, key: Hashable, build_tokens: Callable[[], Any]):
    cached = _PROMPT_CACHE.get(key)
    if cached is not None:
        return cached, "HIT", 0.0, "warm-cache"

    started = time.perf_counter()
    tokens = build_tokens()
    tokenized = time.perf_counter()
    # The 32B H3 encoder fits by itself on the target 22 GiB L4. Materializing
    # it for this cache-miss encode is dramatically faster than streaming its
    # quantized layers through DynamicVRAM for every transformer block. Release
    # it immediately afterwards so FL2VA/REF2VA gets the full VRAM budget.
    with text_encoder_residency(bundle.clip) as residency:
        encode_started = time.perf_counter()
        conditioning = bundle.clip.encode_from_tokens_scheduled(tokens)
        encode_finished = time.perf_counter()
    finished = time.perf_counter()

    _PROMPT_CACHE.put(key, conditioning)
    tokenize_seconds = tokenized - started
    encode_seconds = encode_finished - encode_started
    runtime = (
        f"{residency.summary()}; tokenize={tokenize_seconds:.3f}s; encode={encode_seconds:.3f}s; "
        f"total_miss={finished - started:.3f}s"
    )
    return conditioning, "MISS", finished - started, runtime


def _source_stage(bundle: Any, image: Any, image_id: Hashable, width: int, height: int, source_fit: str):
    from .nodes.image_runtime import _resize_image

    key = _vae_key(bundle), image_id, int(width), int(height), str(source_fit)
    cached = _SOURCE_VAE_CACHE.get(key)
    if cached is not None:
        return (*cached, "HIT")
    fitted = _resize_image(image[:1], width, height, source_fit)
    prewarm_vae(bundle.video_vae)
    latent = bundle.video_vae.encode(fitted)
    value = fitted, latent
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
    key = _vae_key(bundle), image_id, str(reference_size), dimension_key
    cached = _REFERENCE_VAE_CACHE.get(key)
    if cached is not None:
        return (*cached, "HIT")
    if resized_image is None:
        resized_image, tw, th = _reference_resize(image, width, height, reference_size)
    prewarm_vae(bundle.video_vae)
    latent = bundle.video_vae.encode(resized_image)
    value = latent, tw, th
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
    """Build prompt, source/reference VAE, and latent stages independently."""

    import node_helpers

    from .nodes.image_runtime import _prompt_warning, _reference_resize, _resize_image

    width, height = int(studio_context.width), int(studio_context.height)
    prompt = str(studio_context.prompt)
    prompt_key_base = _selected_model_key(bundle, route), route, runtime_mode, _clip_key(bundle), prompt
    image_ids = image_cache_key(studio_context, used_images)
    latent, requested_frames, natural_frames, internal_frames, output_strategy, latent_state = _latent_stage(
        runtime_mode, width, height, frame_preset
    )
    fitted_source = _preview_black(width, height)
    reference_state = "N/A"

    if runtime_mode == "text_to_image (FL2VA)":
        conditioning, text_state, text_seconds, residency = _encode_prompt(
            bundle, (*prompt_key_base, "text-only"), lambda: bundle.clip.tokenize(prompt, images=[])
        )
        checkpoint_note = "Use an FL2VA checkpoint."
    elif runtime_mode == "image_to_image (FL2VA)":
        if not used_images:
            raise ValueError("Image to Image mode requires source_image.")
        source_id = image_ids[0]
        fitted_source, keyframe_latent, source_state = _source_stage(
            bundle, used_images[0], source_id, width, height, source_fit
        )
        reference_state = f"source_vae:{source_state}"
        conditioning, text_state, text_seconds, residency = _encode_prompt(
            bundle,
            (*prompt_key_base, "i2i", source_id, width, height, source_fit),
            lambda: bundle.clip.tokenize(prompt, images=[fitted_source]),
        )
        conditioning = node_helpers.conditioning_set_values(
            conditioning,
            {"minimax_keyframes": [{"resolved_frame_index": 0, "latent": keyframe_latent}], "minimax_frame_count": natural_frames},
        )
        checkpoint_note = "Use an FL2VA checkpoint; frame 0 is the exact source anchor."
    else:
        if not used_images:
            raise ValueError("Reference Edit mode requires source_image as <Picture 1>.")
        preview_key = "ref-preview", image_ids[0], width, height, source_fit
        fitted_source = _PREVIEW_CACHE.get(preview_key)
        if fitted_source is None:
            fitted_source = _resize_image(used_images[0][:1], width, height, source_fit)
            _PREVIEW_CACHE.put(preview_key, fitted_source)
        signatures = tuple(
            (image_id, *_reference_target_size(image, reference_size, width, height))
            for image, image_id in zip(used_images, image_ids, strict=False)
        )
        prompt_key = (*prompt_key_base, "ref2va", signatures, reference_size)
        cached_prompt = _PROMPT_CACHE.get(prompt_key)
        resized_refs = []
        if cached_prompt is None:
            resized_refs = [_reference_resize(image, width, height, reference_size)[0] for image in used_images]
            conditioning, text_state, text_seconds, residency = _encode_prompt(
                bundle,
                prompt_key,
                lambda: bundle.clip.tokenize(
                    prompt, minimax_ref_items=[{"type": "image", "data": image} for image in resized_refs]
                ),
            )
        else:
            conditioning, text_state, text_seconds, residency = cached_prompt, "HIT", 0.0, "warm-cache"
        ref_blocks, ref_states, ref_sizes = [], [], []
        for index, (image, image_id) in enumerate(zip(used_images, image_ids, strict=False)):
            resized = resized_refs[index] if index < len(resized_refs) else None
            latent_ref, tw, th, state = _reference_vae_stage(
                bundle, image, image_id, width, height, reference_size, resized
            )
            ref_blocks.append({"kind": "image", "latent_h": th // 16, "latent_w": tw // 16, "latent": latent_ref})
            ref_states.append(state)
            ref_sizes.append(f"{tw}x{th}")
        reference_state = f"reference_vae:{sum(state == 'HIT' for state in ref_states)}/{len(ref_states)} HIT"
        conditioning = node_helpers.conditioning_set_values(
            conditioning, {"minimax_refs": ref_blocks, "minimax_frame_count": natural_frames}
        )
        checkpoint_note = (
            f"Use a REF2VA checkpoint; {len(used_images)} ordered reference image(s) encoded as "
            f"{', '.join(ref_sizes)} and exposed as <Picture 1> through <Picture {len(used_images)}>."
        )

    trained_note = (
        "beyond the documented 124-362-frame training range"
        if natural_frames > 362
        else "inside the documented 124-362-frame training range"
        if natural_frames >= 124
        else "short experimental temporal packet chosen to reduce image-mode compute"
    )
    decode_note = (
        f"exact {requested_frames}-frame batch"
        if requested_frames == natural_frames
        else f"temporal latent naturally decodes {natural_frames} frames; H3 Exact Frame Decode keeps {requested_frames}"
    )
    runtime_info = (
        f"Mode: {runtime_mode} | temporal profile: {internal_frames} frames | canvas {width}x{height} | "
        f"internal packet {natural_frames} frames | decoded profile {requested_frames} | {decode_note} | "
        f"{trained_note}. {checkpoint_note} Decode only the video latent; the audio VAE is unnecessary for image output. "
        f"Preferred output strategy: {output_strategy}.{_prompt_warning(prompt)}"
    )
    diagnostics = (
        f"text_conditioning={text_state} ({text_seconds:.3f}s) | reference_conditioning={reference_state} | "
        f"latent_prepare={latent_state} | text_encoder_runtime={residency}"
    )
    LOGGER.info("[H3 Studio] Conditioning stages\n  %s", diagnostics)
    return ConditioningStages(conditioning, latent, fitted_source, requested_frames, runtime_info, diagnostics)
