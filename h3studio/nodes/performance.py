"""Drop-in optimized implementations for the Studio's expensive stage boundaries."""

from __future__ import annotations

import logging
import threading
from contextlib import suppress
from typing import Any

from ..lora_stack import apply_custom_lora_stack, normalize_custom_loras
from ..performance import prewarm_diffusion_model, prewarm_vae, tmpfs_pressure_note
from .director import H3StudioContextSamplingPreset
from .image_runtime import H3StudioDecode
from .loader import (
    AUTO_ANALYZER,
    DISABLED_IMAGE_VAE,
    SAME_AS_ANALYZER,
    H3StudioLoader,
)

LOGGER = logging.getLogger(__name__)


_LOADER_CACHE_LOCK = threading.RLock()
_LOADER_CACHE_KEY: tuple[str, ...] | None = None
_LOADER_CACHE_VALUE: tuple[Any, ...] | None = None


def _full_path(category: str, name: str) -> str:
    if not str(name or "").strip() or str(name).strip().lower().startswith(("none", "disabled")):
        return ""
    try:
        import folder_paths

        getter = getattr(folder_paths, "get_full_path_or_raise", None)
        if callable(getter):
            return str(getter(category, name))
        return str(folder_paths.get_full_path(category, name) or "")
    except Exception:
        return ""


def _storage_pressure_for_selection(
    fl2va_model: str,
    ref2va_model: str,
    text_encoder: str,
    video_vae: str,
    image_vae: str,
    image_analyzer: str,
    prompt_writer: str,
) -> None:
    paths = [
        _full_path("diffusion_models", fl2va_model),
        _full_path("diffusion_models", ref2va_model),
        _full_path("text_encoders", text_encoder),
        _full_path("vae", video_vae),
        _full_path("vae", image_vae),
    ]
    # Analyzer/writer selections may be Auto/Same as analyzer rather than a
    # filename, so only include them when folder_paths can resolve them.
    paths.extend([
        _full_path("text_encoders", image_analyzer),
        _full_path("text_encoders", prompt_writer),
    ])
    note = tmpfs_pressure_note(paths)
    if note:
        LOGGER.warning("[H3 Studio] Host-memory pressure: %s", note)


class H3StudioOptimizedLoader(H3StudioLoader):
    """Reuse an unchanged H3 bundle even when ComfyUI recreates the node object."""

    @staticmethod
    def load(
        fl2va_model: str,
        ref2va_model: str,
        text_encoder: str,
        video_vae: str,
        image_vae: str = DISABLED_IMAGE_VAE,
        image_analyzer: str = AUTO_ANALYZER,
        prompt_writer: str = SAME_AS_ANALYZER,
    ):
        key = tuple(map(str, (
            fl2va_model,
            ref2va_model,
            text_encoder,
            video_vae,
            image_vae,
            image_analyzer,
            prompt_writer,
        )))
        global _LOADER_CACHE_KEY, _LOADER_CACHE_VALUE
        with _LOADER_CACHE_LOCK:
            if key == _LOADER_CACHE_KEY and _LOADER_CACHE_VALUE is not None:
                LOGGER.info("[H3 Studio] Model bundle cache hit; reused unchanged CLIP/VAE/bundle objects")
                return _LOADER_CACHE_VALUE
            result = H3StudioLoader.load(
                fl2va_model,
                ref2va_model,
                text_encoder,
                video_vae,
                image_vae,
                image_analyzer,
                prompt_writer,
            )
            _LOADER_CACHE_KEY = key
            _LOADER_CACHE_VALUE = result
        _storage_pressure_for_selection(*key)
        return result


class H3StudioOptimizedContextSamplingPreset(H3StudioContextSamplingPreset):
    """Apply acceleration + custom LoRAs, then pre-materialize the H3 model."""

    def build(self, model, studio_context):
        built_model, sampler, sigmas, info = super().build(model, studio_context)
        profile = str(studio_context.state.generation.sampling_profile)

        reserved: list[str] = []
        with suppress(Exception):
            from ..acceleration import LIGHTX_PROFILES, PDD_PROFILES

            if profile in LIGHTX_PROFILES:
                reserved.append(LIGHTX_PROFILES[profile].lora_filename)
            if profile in PDD_PROFILES:
                reserved.append(PDD_PROFILES[profile].lora_filename)

        custom_specs = normalize_custom_loras(dict(studio_context.state.ui).get("custom_loras", ()))
        if custom_specs:
            built_model, custom_info = apply_custom_lora_stack(
                built_model,
                custom_specs,
                reserved_artifacts=reserved,
            )
            info = f"{info} | {custom_info}"
        else:
            info = f"{info} | custom_loras=none"

        residency = prewarm_diffusion_model(built_model)
        info = f"{info} | {residency.summary()}"
        LOGGER.info("[H3 Studio] Sampling ready\n  %s", info)
        return built_model, sampler, sigmas, info


class H3StudioFastDecode(H3StudioDecode):
    """Fully materialize the selected VAE before H3's internal tiled decoder."""

    def decode(self, samples, vae):
        # H3's decoder is a 36-layer ViT and performs many spatial tile passes.
        # If DynamicVRAM leaves the VAE partially resident, each tile can stream
        # the same weights again. A 5.2 GiB VAE fits comfortably on a 20+ GiB
        # GPU once the diffusion model is evicted, so force that stage handoff.
        residency = prewarm_vae(vae)
        result = super().decode(samples, vae)
        images, decoded_frames, info, recommended_index = result
        info = f"{info} VAE residency: {residency.summary()}."
        LOGGER.info("[H3 Studio - Decode] residency | %s", residency.summary())
        return images, decoded_frames, info, recommended_index
