"""Adaptive maximum-throughput runtime for MiniMax H3 Studio.

The policy is deliberately simple:

* exact conditioning-cache hits do zero model-management work;
* a changed prompt owns exactly one native scheduled text-encoder encode;
* 16 GiB-class GPUs hand stages off aggressively;
* 20-39 GiB GPUs keep diffusion hot through final VAE decode but release the
  32B text encoder after a miss;
* 40 GiB+ GPUs keep text encoder, diffusion and VAE resident whenever ComfyUI
  can do so, turning repeated runs into compute-only work;
* low-host-RAM DynamicVRAM restores ComfyUI's fast-disk mode, which is the same
  policy used by the known-fast L4 baseline;
* component construction is cached independently so CLIP/VAE/UNet loaders never
  serialize behind one unrelated global lock.

No sampler math, quantization recipe, conditioning value or VAE pixel path is
changed here. ComfyUI remains the owner of actual device loading/offloading.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .lora_stack import apply_custom_lora_stack, normalize_custom_loras
from .nodes import loader as loader_module
from .nodes.director import H3StudioContextSamplingPreset
from .nodes.image_runtime import H3StudioDecode
from .nodes.loader import H3StudioLoader, _resolve_text_encoder, clip_choices, vae_choices
from .runtime_handoff import POST_SAMPLE_RELEASE_KEY, attach_sampling_stage_release, release_stage_patcher

LOGGER = logging.getLogger(__name__)
GIB = 1024**3
LOW_HOST_RAM = 48 * GIB
KEEP_DIFFUSION_FOR_VAE = 20 * GIB
KEEP_ALL_HOT = 40 * GIB

_INSTALLED = False
_LOADER_CACHE_LOCK = threading.RLock()
_LOADER_CACHE_KEY: tuple[str, ...] | None = None
_LOADER_CACHE_VALUE: tuple[Any, ...] | None = None
_CLIP_LOCK = threading.RLock()
_VAE_LOCK = threading.RLock()
_UNET_LOCK = threading.RLock()
_CLIP_CACHE: dict[str, Any] = {}
_VAE_CACHE: dict[str, Any] = {}
_UNET_CACHE: dict[str, Any] = {}
_PREWARM_LOCK = threading.RLock()
_PREWARM_STARTED = False
_PREWARM_DONE = threading.Event()
_PREWARM_ERROR = ""

_ORIGINAL_LOAD_CLIP = loader_module._load_clip
_ORIGINAL_LOAD_VAE = loader_module._load_vae
_ORIGINAL_LOAD_UNET = loader_module._load_unet


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class HardwarePolicy:
    total_vram: int
    total_ram: int
    keep_diffusion_for_vae: bool
    keep_all_hot: bool
    low_host_ram: bool

    @property
    def label(self) -> str:
        if self.keep_all_hot:
            return "resident-high-vram"
        if self.keep_diffusion_for_vae:
            return "hot-diffusion-staged-text"
        return "strict-stage-handoff"


@lru_cache(maxsize=1)
def hardware_policy() -> HardwarePolicy:
    total_vram = 0
    total_ram = 0
    try:
        import psutil

        total_ram = int(psutil.virtual_memory().total)
    except Exception:
        pass
    try:
        import comfy.model_management as mm

        device = mm.get_torch_device()
        total_vram = int(mm.get_total_memory(device))
    except Exception:
        try:
            import torch

            if torch.cuda.is_available():
                total_vram = int(torch.cuda.get_device_properties(torch.cuda.current_device()).total_memory)
        except Exception:
            pass

    return HardwarePolicy(
        total_vram=total_vram,
        total_ram=total_ram,
        keep_diffusion_for_vae=total_vram >= KEEP_DIFFUSION_FOR_VAE,
        keep_all_hot=total_vram >= KEEP_ALL_HOT,
        low_host_ram=bool(total_ram and total_ram <= LOW_HOST_RAM),
    )


def _configure_comfy_for_speed() -> None:
    """Restore the known-fast low-RAM DynamicVRAM policy without forcing it elsewhere."""

    policy = hardware_policy()
    try:
        import comfy.model_management as mm

        args = getattr(mm, "args", None)
        if (
            args is not None
            and policy.low_host_ram
            and not _env_flag("H3STUDIO_DISABLE_AUTO_FAST_DISK")
            and not bool(getattr(args, "high_ram", False))
            and not bool(getattr(args, "fast_disk", False))
        ):
            args.fast_disk = True
            LOGGER.warning(
                "[H3 Studio] Max-speed policy: low host RAM %.1f GiB -> ComfyUI fast-disk enabled for DynamicVRAM",
                policy.total_ram / GIB,
            )
    except Exception as exc:
        LOGGER.debug("[H3 Studio] fast-disk auto policy unavailable: %s", exc)

    LOGGER.info(
        "[H3 Studio] Max-speed hardware policy | mode=%s | vram=%.1fGiB | ram=%.1fGiB | keep_diffusion_for_vae=%s | keep_all_hot=%s",
        policy.label,
        policy.total_vram / GIB,
        policy.total_ram / GIB,
        policy.keep_diffusion_for_vae,
        policy.keep_all_hot,
    )


def _cached_clip(name: str):
    key = str(name)
    with _CLIP_LOCK:
        cached = _CLIP_CACHE.get(key)
        if cached is not None:
            LOGGER.info("[H3 Studio] text encoder object cache HIT | %s", key)
            return cached
        started = time.perf_counter()
        value = _ORIGINAL_LOAD_CLIP(name)
        _CLIP_CACHE[key] = value
        LOGGER.info("[H3 Studio] text encoder object cached | %s | %.3fs", key, time.perf_counter() - started)
        return value


def _cached_vae(name: str):
    key = str(name)
    with _VAE_LOCK:
        cached = _VAE_CACHE.get(key)
        if cached is not None:
            LOGGER.info("[H3 Studio] VAE object cache HIT | %s", key)
            return cached
        started = time.perf_counter()
        value = _ORIGINAL_LOAD_VAE(name)
        _VAE_CACHE[key] = value
        LOGGER.info("[H3 Studio] VAE object cached | %s | %.3fs", key, time.perf_counter() - started)
        return value


def _cached_unet(name: str):
    key = str(name)
    with _UNET_LOCK:
        cached = _UNET_CACHE.get(key)
        if cached is not None:
            LOGGER.info("[H3 Studio] transformer object cache HIT | %s", key)
            return cached
        started = time.perf_counter()
        value = _ORIGINAL_LOAD_UNET(name)
        _UNET_CACHE[key] = value
        LOGGER.info("[H3 Studio] transformer object cached | %s | %.3fs", key, time.perf_counter() - started)
        return value


def _install_component_caches() -> None:
    loader_module._load_clip = _cached_clip
    loader_module._load_vae = _cached_vae
    loader_module._load_unet = _cached_unet


def _install_conditioning_fastpath() -> None:
    """One TE load owner, zero warm-hit work, no explicit sync/cache flushes."""

    from . import conditioning_cache

    current = conditioning_cache._encode_prompt
    if bool(getattr(current, "__h3studio_max_speed_v5__", False)):
        return

    def encode_prompt(bundle: Any, key: Any, build_tokens):
        cached = conditioning_cache._PROMPT_CACHE.get(key)
        if cached is not None:
            return cached, "HIT", 0.0, "max-speed-v5; cache=hit; model_management=zero"

        policy = hardware_policy()
        started = time.perf_counter()
        diffusion_release = "kept-hot"
        if not policy.keep_all_hot:
            result = release_stage_patcher(getattr(bundle, "_model", None), label="pre_text_diffusion")
            diffusion_release = result.mode

        tokens = build_tokens()
        tokenized = time.perf_counter()
        encode_started = time.perf_counter()
        conditioning = bundle.clip.encode_from_tokens_scheduled(tokens)
        encoded = time.perf_counter()

        text_release = "kept-hot"
        if not policy.keep_all_hot:
            patcher = getattr(bundle.clip, "patcher", None)
            text_release = release_stage_patcher(patcher, label="text_encoder").mode

        conditioning_cache._PROMPT_CACHE.put(key, conditioning)
        finished = time.perf_counter()
        runtime = (
            "max-speed-v5; single-scheduled-text-encode; "
            f"tokenize={tokenized - started:.3f}s; encode={encoded - encode_started:.3f}s; "
            f"post={finished - encoded:.3f}s; diffusion={diffusion_release}; text_encoder={text_release}; "
            f"policy={policy.label}"
        )
        return conditioning, "MISS", finished - started, runtime

    encode_prompt.__h3studio_max_speed_v5__ = True
    conditioning_cache._encode_prompt = encode_prompt


def _remove_sampling_release(model: Any) -> None:
    try:
        import comfy.patcher_extension

        model.remove_wrappers_with_key(comfy.patcher_extension.WrappersMP.OUTER_SAMPLE, POST_SAMPLE_RELEASE_KEY)
    except Exception:
        pass


def _remove_force_full_experiment(model: Any) -> None:
    try:
        import comfy.patcher_extension

        from .runtime_stability import SAMPLING_RESIDENCY_WRAPPER_KEY

        model.remove_wrappers_with_key(
            comfy.patcher_extension.WrappersMP.PREPARE_SAMPLING,
            SAMPLING_RESIDENCY_WRAPPER_KEY,
        )
    except Exception:
        pass


class H3StudioMaxSpeedLoader(H3StudioLoader):
    """Cache unchanged bundle/components without changing selected model semantics."""

    @staticmethod
    def load(
        fl2va_model: str,
        ref2va_model: str,
        text_encoder: str,
        video_vae: str,
        image_vae: str = loader_module.DISABLED_IMAGE_VAE,
        image_analyzer: str = loader_module.AUTO_ANALYZER,
        prompt_writer: str = loader_module.SAME_AS_ANALYZER,
    ):
        global _LOADER_CACHE_KEY, _LOADER_CACHE_VALUE
        key = tuple(map(str, (fl2va_model, ref2va_model, text_encoder, video_vae, image_vae, image_analyzer, prompt_writer)))
        with _LOADER_CACHE_LOCK:
            if key == _LOADER_CACHE_KEY and _LOADER_CACHE_VALUE is not None:
                LOGGER.info("[H3 Studio] Model bundle cache HIT")
                return _LOADER_CACHE_VALUE
            started = time.perf_counter()
            value = H3StudioLoader.load(
                fl2va_model,
                ref2va_model,
                text_encoder,
                video_vae,
                image_vae,
                image_analyzer,
                prompt_writer,
            )
            _LOADER_CACHE_KEY = key
            _LOADER_CACHE_VALUE = value
            LOGGER.info("[H3 Studio] Model bundle ready | %.3fs", time.perf_counter() - started)
            return value


class H3StudioMaxSpeedSamplingPreset(H3StudioContextSamplingPreset):
    """Preserve all acceleration/custom-LoRA behavior and let native Comfy own residency."""

    def build(self, model, studio_context):
        from .acceleration import LIGHTX_PROFILES, PDD_PROFILES, is_pdd_profile

        profile = str(studio_context.state.generation.sampling_profile)
        custom_specs = normalize_custom_loras(dict(studio_context.state.ui).get("custom_loras", ()))
        accelerated = profile in LIGHTX_PROFILES or is_pdd_profile(profile)
        reserved: list[str] = []
        if profile in LIGHTX_PROFILES:
            reserved.append(LIGHTX_PROFILES[profile].lora_filename)
        if profile in PDD_PROFILES:
            reserved.append(PDD_PROFILES[profile].lora_filename)

        if custom_specs and not accelerated:
            from .nodes.director import SAMPLING_PROFILE_TO_RUNTIME, _sampling_profile
            from .nodes.image_runtime import H3StudioSamplingPreset

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

        _remove_force_full_experiment(built_model)
        policy = hardware_policy()
        if policy.keep_diffusion_for_vae:
            _remove_sampling_release(built_model)
            handoff = "keep-hot"
        else:
            handoff = attach_sampling_stage_release(built_model)

        seed = int(getattr(studio_context.state.generation, "seed", 0))
        info = (
            f"{info} | sampling_residency=native-comfy-manager | post_sample={handoff} | "
            f"policy={policy.label} | seed={seed}"
        )
        LOGGER.info("[H3 Studio] Sampling max-speed ready | %s", info)
        return built_model, sampler, sigmas, info


class H3StudioMaxSpeedDecode(H3StudioDecode):
    """Use exact native H3 VAE decode and keep only useful residency afterward."""

    def decode(self, samples, vae):
        policy = hardware_policy()
        started = time.perf_counter()
        result = H3StudioDecode.decode(self, samples, vae)
        release = "kept-hot"
        if not policy.keep_all_hot:
            release = release_stage_patcher(getattr(vae, "patcher", None), label="final_vae").mode
        images, decoded_frames, info, recommended_index = result
        info = (
            f"{info} Max-speed policy={policy.label}; final_vae={release}; "
            f"stage={time.perf_counter() - started:.3f}s."
        )
        LOGGER.info(
            "[H3 Studio] Decode max-speed complete | policy=%s | final_vae=%s | %.3fs",
            policy.label,
            release,
            time.perf_counter() - started,
        )
        return images, decoded_frames, info, recommended_index


def start_component_prewarm() -> str:
    """Hide first-click CLIP/VAE construction behind server idle time."""

    global _PREWARM_STARTED, _PREWARM_ERROR
    if _env_flag("H3STUDIO_DISABLE_STARTUP_PREWARM"):
        return "disabled-by-env"

    with _PREWARM_LOCK:
        if _PREWARM_STARTED:
            return "already-started"
        _PREWARM_STARTED = True
        _PREWARM_DONE.clear()

        def worker() -> None:
            global _PREWARM_ERROR
            started = time.perf_counter()
            try:
                clips = clip_choices()
                vaes = vae_choices()
                if not clips or not vaes:
                    return
                clip_name = _resolve_text_encoder(clips[0])
                vae_name = vaes[0]
                LOGGER.info(
                    "[H3 Studio] Max-speed background prewarm | CLIP=%s | VAE=%s | diffusion=lazy",
                    clip_name,
                    vae_name,
                )
                clip = _cached_clip(clip_name)
                vae = _cached_vae(vae_name)

                policy = hardware_policy()
                if policy.keep_all_hot and not _env_flag("H3STUDIO_DISABLE_GPU_PREWARM"):
                    import comfy.model_management as mm

                    patchers = [
                        patcher
                        for patcher in (getattr(clip, "patcher", None), getattr(vae, "patcher", None))
                        if patcher is not None
                    ]
                    if patchers:
                        mm.load_models_gpu(patchers, force_full_load=True)
                        LOGGER.info("[H3 Studio] High-VRAM CLIP/VAE GPU prewarm complete")
            except Exception as exc:
                _PREWARM_ERROR = f"{type(exc).__name__}: {exc}"
                LOGGER.warning("[H3 Studio] Background prewarm failed nonfatally: %s", _PREWARM_ERROR)
            finally:
                _PREWARM_DONE.set()
                LOGGER.info("[H3 Studio] Background prewarm finished in %.3fs", time.perf_counter() - started)

        threading.Thread(target=worker, name="H3StudioMaxSpeedPrewarm", daemon=True).start()
        return "background-started"


def install_max_speed_runtime() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _configure_comfy_for_speed()
    _install_component_caches()
    _install_conditioning_fastpath()
    _INSTALLED = True


__all__ = [
    "H3StudioMaxSpeedDecode",
    "H3StudioMaxSpeedLoader",
    "H3StudioMaxSpeedSamplingPreset",
    "HardwarePolicy",
    "hardware_policy",
    "install_max_speed_runtime",
    "start_component_prewarm",
]
