"""Drop-in optimized implementations for the Studio's expensive stage boundaries."""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..lora_stack import apply_custom_lora_stack, normalize_custom_loras
from ..performance import tmpfs_pressure_note, vae_full_stage
from .director import H3StudioContextSamplingPreset
from .image_runtime import H3StudioDecode
from .loader import (
    AUTO_ANALYZER,
    DISABLED_IMAGE_VAE,
    SAME_AS_ANALYZER,
    H3StudioLoader,
    _resolve_text_encoder,
)

LOGGER = logging.getLogger(__name__)


_LOADER_CACHE_LOCK = threading.RLock()
_LOADER_CACHE_KEY: tuple[str, ...] | None = None
_LOADER_CACHE_VALUE: tuple[Any, ...] | None = None
_PATH_PRIORITY_LOCK = threading.RLock()


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


def _is_tmpfs_path(value: str | Path) -> bool:
    try:
        path = Path(value).resolve()
    except OSError:
        path = Path(value)
    tmpfs = Path("/dev/shm")
    return path == tmpfs or tmpfs in path.parents


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
    paths.extend([
        _full_path("text_encoders", image_analyzer),
        _full_path("text_encoders", prompt_writer),
    ])
    note = tmpfs_pressure_note(paths)
    if note:
        LOGGER.warning("[H3 Studio] Host-memory pressure: %s", note)


@contextmanager
def _prefer_persistent_model_source(category: str, name: str):
    """Prefer an existing disk-backed duplicate over a real /dev/shm copy.

    Lightning H3 launchers can register RAM-cache folders ahead of normal model
    folders. On a 32 GiB host a 15 GiB text-encoder file in tmpfs competes with
    the staged model itself and can turn safetensor construction into minutes of
    memory pressure. If ComfyUI already knows a persistent duplicate of the
    exact same relative filename, temporarily move that root to the front only
    for this load. Symlinks into persistent storage are left alone because their
    resolved path is already disk-backed.
    """

    if not str(name or "").strip():
        yield ""
        return

    try:
        import folder_paths

        mapped = folder_paths.map_legacy(category)
        current = folder_paths.get_full_path(mapped, name)
    except Exception:
        yield ""
        return

    if not current or not _is_tmpfs_path(current):
        yield str(current or "")
        return

    with _PATH_PRIORITY_LOCK:
        try:
            roots, _extensions = folder_paths.folder_names_and_paths[mapped]
        except Exception:
            yield str(current)
            return

        original = list(roots)
        chosen_root = ""
        chosen_path = ""
        relative = str(name).replace("\\", "/")
        for root in original:
            candidate = Path(root) / relative
            try:
                if candidate.is_file() and not _is_tmpfs_path(candidate):
                    chosen_root = root
                    chosen_path = str(candidate.resolve())
                    break
            except OSError:
                continue

        if not chosen_root:
            LOGGER.warning(
                "[H3 Studio] %s resolves to real tmpfs (%s), but no registered disk-backed duplicate exists. "
                "On low-RAM hosts this can dominate cold-load time.",
                name,
                current,
            )
            yield str(current)
            return

        roots[:] = [chosen_root, *[root for root in original if root != chosen_root]]
        LOGGER.info(
            "[H3 Studio] Model source override | %s -> %s (avoiding /dev/shm pressure)",
            current,
            chosen_path,
        )
        try:
            yield chosen_path
        finally:
            roots[:] = original


class H3StudioOptimizedLoader(H3StudioLoader):
    """Reuse an unchanged H3 bundle and avoid pathological tmpfs cold loads."""

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

            resolved_text_encoder = _resolve_text_encoder(text_encoder)
            # Diagnose before loading. Previously this warning ran only after a
            # multi-minute CLIP construction had already completed.
            _storage_pressure_for_selection(
                fl2va_model,
                ref2va_model,
                resolved_text_encoder,
                video_vae,
                image_vae,
                image_analyzer,
                prompt_writer,
            )

            started = time.perf_counter()
            with _prefer_persistent_model_source("text_encoders", resolved_text_encoder), _prefer_persistent_model_source(
                "vae", video_vae
            ):
                result = H3StudioLoader.load(
                    fl2va_model,
                    ref2va_model,
                    text_encoder,
                    video_vae,
                    image_vae,
                    image_analyzer,
                    prompt_writer,
                )
            elapsed = time.perf_counter() - started
            LOGGER.info("[H3 Studio] Model bundle constructed in %.3fs", elapsed)
            _LOADER_CACHE_KEY = key
            _LOADER_CACHE_VALUE = result
        return result


class H3StudioOptimizedContextSamplingPreset(H3StudioContextSamplingPreset):
    """Apply acceleration and custom LoRAs without taking over model residency."""

    def build(self, model, studio_context):
        profile = str(studio_context.state.generation.sampling_profile)
        custom_specs = normalize_custom_loras(dict(studio_context.state.ui).get("custom_loras", ()))

        from ..acceleration import LIGHTX_PROFILES, PDD_PROFILES, is_pdd_profile

        accelerated = profile in LIGHTX_PROFILES or is_pdd_profile(profile)
        reserved: list[str] = []
        if profile in LIGHTX_PROFILES:
            reserved.append(LIGHTX_PROFILES[profile].lora_filename)
        if profile in PDD_PROFILES:
            reserved.append(PDD_PROFILES[profile].lora_filename)

        if custom_specs and not accelerated:
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

        info = f"{info} | sampling_residency=native-comfy-manager"
        LOGGER.info("[H3 Studio] Sampling ready\n  %s", info)
        return built_model, sampler, sigmas, info


class H3StudioFastDecode(H3StudioDecode):
    """Legacy-core decode fallback with one native full-VAE stage."""

    def decode(self, samples, vae):
        started = time.perf_counter()
        with vae_full_stage(vae, label="vae_decode") as residency:
            result = super().decode(samples, vae)
        elapsed = time.perf_counter() - started
        images, decoded_frames, info, recommended_index = result
        residency.load_seconds = elapsed
        info = f"{info} VAE decode runtime: {residency.summary()}."
        LOGGER.info("[H3 Studio - Decode] %s", residency.summary())
        return images, decoded_frames, info, recommended_index
