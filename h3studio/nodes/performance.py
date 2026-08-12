"""Drop-in optimized implementations for the Studio's expensive stage boundaries."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from ..lora_stack import apply_custom_lora_stack, normalize_custom_loras
from ..performance import attach_sampling_residency_policy, tmpfs_pressure_note, vae_full_stage
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


def _artifact_bytes(category: str, names: list[str]) -> int:
    """Return unique on-disk bytes for selected artifacts when resolvable."""

    total = 0
    seen: set[str] = set()
    for name in names:
        path = _full_path(category, name)
        if not path:
            continue
        try:
            resolved = str(Path(path).resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            total += int(Path(resolved).stat().st_size)
        except OSError:
            continue
    return total


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
    """Apply acceleration + custom LoRAs, then defer residency to sampler preparation."""

    def build(self, model, studio_context):
        profile = str(studio_context.state.generation.sampling_profile)
        custom_specs = normalize_custom_loras(dict(studio_context.state.ui).get("custom_loras", ()))

        from ..acceleration import LIGHTX_PROFILES, PDD_PROFILES, is_pdd_profile

        accelerated = profile in LIGHTX_PROFILES or is_pdd_profile(profile)
        reserved: list[str] = []
        adapter_names: list[str] = []
        if profile in LIGHTX_PROFILES:
            filename = LIGHTX_PROFILES[profile].lora_filename
            reserved.append(filename)
            adapter_names.append(filename)
        if profile in PDD_PROFILES:
            filename = PDD_PROFILES[profile].lora_filename
            reserved.append(filename)
            adapter_names.append(filename)

        if custom_specs and not accelerated:
            # Base sampling creates a shifted ModelPatcher clone. Apply custom
            # LoRAs to the stable base patcher first so prompt/seed reruns hit
            # the stack cache instead of reloading the same adapter files.
            from .director import SAMPLING_PROFILE_TO_RUNTIME, _sampling_profile
            from .image_runtime import H3StudioSamplingPreset

            base_model, custom_info = apply_custom_lora_stack(model, custom_specs)
            runtime_profile = SAMPLING_PROFILE_TO_RUNTIME[_sampling_profile(profile)]
            built_model, sampler, sigmas, info = H3StudioSamplingPreset().build(base_model, runtime_profile)
            info = f"{info} | {custom_info}"
        else:
            built_model, sampler, sigmas, info = super().build(model, studio_context)
            if custom_specs:
                built_model, custom_info = apply_custom_lora_stack(
                    built_model,
                    custom_specs,
                    reserved_artifacts=reserved,
                )
                info = f"{info} | {custom_info}"
            else:
                info = f"{info} | custom_loras=none"

        adapter_names.extend(spec.name for spec in custom_specs)
        adapter_bytes = _artifact_bytes("loras", adapter_names)

        # Do not eagerly force the transformer onto the GPU here. ComfyUI has
        # not yet calculated the real activation reservation, so an eager full
        # load can be immediately evicted and loaded a second time at KSampler's
        # ``Model Initializing`` boundary. Attach an idempotent PREPARE_SAMPLING
        # wrapper to this *same stable patcher* instead; it decides full-vs-
        # dynamic residency once, using the actual latent/conditioning budget.
        residency = attach_sampling_residency_policy(
            built_model,
            adapter_bytes=adapter_bytes,
            profile=profile,
        )
        info = f"{info} | {residency.summary()}"
        LOGGER.info("[H3 Studio] Sampling ready\n  %s", info)
        return built_model, sampler, sigmas, info


class H3StudioFastDecode(H3StudioDecode):
    """Decode with one native full-VAE handoff instead of eager double loading."""

    def decode(self, samples, vae):
        # ComfyUI's VAE.decode already knows the exact H3 activation budget and
        # the H3 video VAE already owns its spatial/temporal tiling. Temporarily
        # requesting native full residency at that exact boundary keeps the
        # ~5 GiB decoder weights resident across all internal tile passes without
        # the previous eager-prewarm -> second manager-load cycle.
        started = time.perf_counter()
        with vae_full_stage(vae, label="vae_decode") as residency:
            result = super().decode(samples, vae)
        elapsed = time.perf_counter() - started
        images, decoded_frames, info, recommended_index = result
        residency.load_seconds = elapsed
        info = f"{info} VAE decode runtime: {residency.summary()}."
        LOGGER.info("[H3 Studio - Decode] %s", residency.summary())
        return images, decoded_frames, info, recommended_index
