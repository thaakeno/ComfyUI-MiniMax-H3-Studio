"""Drop-in optimized implementations for the Studio's expensive stage boundaries."""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..lora_stack import apply_custom_lora_stack, normalize_custom_loras
from ..performance import tmpfs_pressure_note, vae_full_stage
from . import loader as loader_module
from .director import H3StudioContextSamplingPreset
from .image_runtime import H3StudioDecode
from .loader import (
    AUTO_ANALYZER,
    DISABLED_IMAGE_VAE,
    SAME_AS_ANALYZER,
    H3StudioLoader,
    _resolve_text_encoder,
    clip_choices,
    vae_choices,
)

LOGGER = logging.getLogger(__name__)


_LOADER_CACHE_LOCK = threading.RLock()
_LOADER_CACHE_KEY: tuple[str, ...] | None = None
_LOADER_CACHE_VALUE: tuple[Any, ...] | None = None
_PATH_PRIORITY_LOCK = threading.RLock()
_COMPONENT_CACHE_LOCK = threading.RLock()
_CLIP_COMPONENT_CACHE: dict[str, Any] = {}
_VAE_COMPONENT_CACHE: dict[str, Any] = {}
_COMPONENT_CACHE_INSTALLED = False
_PREWARM_STATE_LOCK = threading.RLock()
_PREWARM_DONE = threading.Event()
_PREWARM_THREAD: threading.Thread | None = None
_PREWARM_STARTED = False
_PREWARM_ERROR = ""


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


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


def _install_component_cache() -> None:
    """Make H3 CLIP/VAE construction process-wide and reusable by every bundle."""

    global _COMPONENT_CACHE_INSTALLED
    with _COMPONENT_CACHE_LOCK:
        if _COMPONENT_CACHE_INSTALLED:
            return
        original_clip_loader = loader_module._load_clip
        original_vae_loader = loader_module._load_vae

        def cached_clip_loader(name: str):
            key = str(name)
            with _COMPONENT_CACHE_LOCK:
                cached = _CLIP_COMPONENT_CACHE.get(key)
                if cached is not None:
                    LOGGER.info("[H3 Studio] H3 text-encoder object cache hit | %s", key)
                    return cached
                # Keep the lock through construction. A foreground prompt that
                # arrives during startup prewarm waits for this same object
                # instead of starting a second 15+ GiB construction.
                started = time.perf_counter()
                value = original_clip_loader(name)
                _CLIP_COMPONENT_CACHE[key] = value
                LOGGER.info(
                    "[H3 Studio] H3 text-encoder object cached | %s | %.3fs",
                    key,
                    time.perf_counter() - started,
                )
                return value

        def cached_vae_loader(name: str):
            key = str(name)
            with _COMPONENT_CACHE_LOCK:
                cached = _VAE_COMPONENT_CACHE.get(key)
                if cached is not None:
                    LOGGER.info("[H3 Studio] H3 VAE object cache hit | %s", key)
                    return cached
                started = time.perf_counter()
                value = original_vae_loader(name)
                _VAE_COMPONENT_CACHE[key] = value
                LOGGER.info(
                    "[H3 Studio] H3 VAE object cached | %s | %.3fs",
                    key,
                    time.perf_counter() - started,
                )
                return value

        cached_clip_loader.__h3studio_component_cache__ = True
        cached_vae_loader.__h3studio_component_cache__ = True
        loader_module._load_clip = cached_clip_loader
        loader_module._load_vae = cached_vae_loader
        _COMPONENT_CACHE_INSTALLED = True


_install_component_cache()


class H3StudioOptimizedLoader(H3StudioLoader):
    """Reuse unchanged H3 objects and avoid pathological tmpfs cold loads."""

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
        key = tuple(
            map(
                str,
                (
                    fl2va_model,
                    ref2va_model,
                    text_encoder,
                    video_vae,
                    image_vae,
                    image_analyzer,
                    prompt_writer,
                ),
            )
        )
        global _LOADER_CACHE_KEY, _LOADER_CACHE_VALUE
        with _LOADER_CACHE_LOCK:
            if key == _LOADER_CACHE_KEY and _LOADER_CACHE_VALUE is not None:
                LOGGER.info("[H3 Studio] Model bundle cache hit; reused unchanged CLIP/VAE/bundle objects")
                return _LOADER_CACHE_VALUE

            resolved_text_encoder = _resolve_text_encoder(text_encoder)
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


def start_default_bundle_prewarm() -> str:
    """Construct the default H3 text encoder and video VAE in the background.

    Component-level caching is deliberate: the warm objects are reused even if
    the workflow later selects a different FL2VA/REF2VA diffusion checkpoint.
    Diffusion itself stays lazy so idle prewarm cannot consume another ~12 GiB.
    """

    global _PREWARM_STARTED, _PREWARM_THREAD, _PREWARM_ERROR

    if _env_flag("H3STUDIO_DISABLE_STARTUP_PREWARM"):
        return "disabled-by-env"

    with _PREWARM_STATE_LOCK:
        if _PREWARM_STARTED:
            return "already-started"
        try:
            clips = clip_choices()
            vaes = vae_choices()
            if not clips or not vaes:
                raise RuntimeError("default H3 text encoder or video VAE is unavailable")
            text_encoder = _resolve_text_encoder(clips[0])
            video_vae = vaes[0]
        except Exception as exc:
            _PREWARM_ERROR = f"{type(exc).__name__}: {exc}"
            _PREWARM_DONE.set()
            LOGGER.info("[H3 Studio] Startup component prewarm skipped: %s", _PREWARM_ERROR)
            return "unavailable"

        _PREWARM_STARTED = True
        _PREWARM_DONE.clear()

        def worker() -> None:
            global _PREWARM_ERROR
            started = time.perf_counter()
            LOGGER.info(
                "[H3 Studio] Startup component prewarm started | text_encoder=%s | video_vae=%s | diffusion=lazy",
                text_encoder,
                video_vae,
            )
            try:
                with _prefer_persistent_model_source("text_encoders", text_encoder):
                    loader_module._load_clip(text_encoder)
                with _prefer_persistent_model_source("vae", video_vae):
                    loader_module._load_vae(video_vae)
            except Exception as exc:
                _PREWARM_ERROR = f"{type(exc).__name__}: {exc}"
                LOGGER.warning("[H3 Studio] Startup component prewarm failed nonfatally: %s", _PREWARM_ERROR)
            else:
                LOGGER.info(
                    "[H3 Studio] Startup component prewarm complete in %.3fs; first prompt reuses warm CLIP/VAE objects",
                    time.perf_counter() - started,
                )
            finally:
                _PREWARM_DONE.set()

        _PREWARM_THREAD = threading.Thread(target=worker, name="h3studio-startup-prewarm", daemon=True)
        _PREWARM_THREAD.start()
        return "background-started"
