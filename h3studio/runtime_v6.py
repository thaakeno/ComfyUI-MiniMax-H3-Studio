"""Native-first maximum-throughput runtime for MiniMax H3 Studio.

v6 deliberately removes the v5 startup prewarm and global component-object
caches. ComfyUI already caches an unchanged H3StudioLoader node, and the bundle
itself already keeps the selected transformer object. Re-implementing that with
background CLIP/VAE construction added lock contention, persistent objects and
startup I/O without helping seed-only reruns.

The v6 policy therefore keeps only the changes that are useful on the hot path:

* exact prompt cache hits do no model-management work;
* a prompt miss uses the original native Comfy scheduled text encode exactly
  once, with only a clean diffusion handoff before it when needed;
* low-host-RAM systems may use ComfyUI's known-fast fast-disk DynamicVRAM path;
* seed-only reruns keep the diffusion model hot on 20 GiB+ GPUs;
* final VAE residency is released on sub-40 GiB hardware;
* no model is constructed or moved merely because ComfyUI started.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .lora_stack import apply_custom_lora_stack, normalize_custom_loras
from .nodes import loader as loader_module
from .nodes.director import H3StudioContextSamplingPreset
from .nodes.image_runtime import H3StudioDecode
from .nodes.loader import H3StudioLoader
from .runtime_handoff import POST_SAMPLE_RELEASE_KEY, attach_sampling_stage_release, release_stage_patcher
from .runtime_trace import emit

LOGGER = logging.getLogger(__name__)
GIB = 1024**3
LOW_HOST_RAM = 48 * GIB
KEEP_DIFFUSION_HOT = 20 * GIB
KEEP_ALL_HOT = 40 * GIB
_INSTALLED = False


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _key_digest(value: Any) -> str:
    return hashlib.sha1(repr(value).encode("utf-8", errors="replace")).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class HardwarePolicy:
    total_vram: int
    total_ram: int
    keep_diffusion_hot: bool
    keep_all_hot: bool
    low_host_ram: bool

    @property
    def label(self) -> str:
        if self.keep_all_hot:
            return "resident-high-vram"
        if self.keep_diffusion_hot:
            return "hot-diffusion-native-stages"
        return "strict-native-stage-handoff"


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

    policy = HardwarePolicy(
        total_vram=total_vram,
        total_ram=total_ram,
        keep_diffusion_hot=total_vram >= KEEP_DIFFUSION_HOT,
        keep_all_hot=total_vram >= KEEP_ALL_HOT,
        low_host_ram=bool(total_ram and total_ram <= LOW_HOST_RAM),
    )
    emit(
        "v6.policy.detected",
        memory=True,
        policy=policy.label,
        total_vram_gib=policy.total_vram / GIB,
        total_ram_gib=policy.total_ram / GIB,
        keep_diffusion_hot=policy.keep_diffusion_hot,
        keep_all_hot=policy.keep_all_hot,
        low_host_ram=policy.low_host_ram,
    )
    return policy


def _configure_comfy_for_speed() -> None:
    policy = hardware_policy()
    fast_disk_before = False
    fast_disk_after = False
    high_ram = False
    try:
        import comfy.model_management as mm

        args = getattr(mm, "args", None)
        if args is not None:
            fast_disk_before = bool(getattr(args, "fast_disk", False))
            high_ram = bool(getattr(args, "high_ram", False))
        if (
            args is not None
            and policy.low_host_ram
            and not _env_flag("H3STUDIO_DISABLE_AUTO_FAST_DISK")
            and not high_ram
            and not fast_disk_before
        ):
            args.fast_disk = True
            LOGGER.warning(
                "[H3 Studio] v6 low-RAM policy: %.1f GiB host RAM -> ComfyUI fast-disk enabled",
                policy.total_ram / GIB,
            )
        if args is not None:
            fast_disk_after = bool(getattr(args, "fast_disk", False))
    except Exception as exc:
        emit("v6.policy.fast_disk.error", error_type=type(exc).__name__, error=str(exc))

    emit(
        "v6.policy.configured",
        memory=True,
        policy=policy.label,
        fast_disk_before=fast_disk_before,
        fast_disk_after=fast_disk_after,
        high_ram=high_ram,
        startup_prewarm=False,
        component_monkeypatch_cache=False,
    )


def _install_native_conditioning_guard() -> None:
    """Preserve the native conditioning implementation; only clean diffusion on misses."""

    from . import conditioning_cache

    current = conditioning_cache._encode_prompt
    if bool(getattr(current, "__h3studio_native_v6__", False)):
        return
    native_encode = current

    def encode_prompt(bundle: Any, key: Any, build_tokens):
        key_hash = _key_digest(key)
        cached = conditioning_cache._PROMPT_CACHE.get(key)
        if cached is not None:
            emit(
                "v6.conditioning.hit",
                memory=True,
                key=key_hash,
                model_management="zero",
            )
            return cached, "HIT", 0.0, "native-v6; cache=hit; model_management=zero"

        policy = hardware_policy()
        started = time.perf_counter()
        diffusion = getattr(bundle, "_model", None)
        diffusion_handoff = "not-loaded"
        if diffusion is not None and not policy.keep_all_hot:
            release_started = time.perf_counter()
            release = release_stage_patcher(diffusion, label="pre_text_diffusion")
            diffusion_handoff = release.mode
            emit(
                "v6.conditioning.pre_text_diffusion",
                memory=True,
                key=key_hash,
                elapsed_s=time.perf_counter() - release_started,
                mode=release.mode,
                loaded_before_gib=release.loaded_before / GIB,
                loaded_after_gib=release.loaded_after / GIB,
            )

        emit(
            "v6.conditioning.native_encode.begin",
            memory=True,
            key=key_hash,
            policy=policy.label,
            diffusion_handoff=diffusion_handoff,
        )
        result = native_encode(bundle, key, build_tokens)
        emit(
            "v6.conditioning.native_encode.end",
            memory=True,
            key=key_hash,
            elapsed_s=time.perf_counter() - started,
            cache_state=result[1],
            native_runtime=result[3],
            policy=policy.label,
        )
        return result

    encode_prompt.__h3studio_native_v6__ = True
    conditioning_cache._encode_prompt = encode_prompt
    emit("v6.conditioning.install", result="native-wrapper-installed")


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


class H3StudioNativeLoader(H3StudioLoader):
    """Native H3 loader with timing only; no global object cache and no prewarm."""

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
        started = time.perf_counter()
        emit(
            "v6.loader.begin",
            memory=True,
            fl2va=fl2va_model,
            ref2va=ref2va_model,
            text_encoder=text_encoder,
            video_vae=video_vae,
            startup=False,
        )
        try:
            result = H3StudioLoader.load(
                fl2va_model,
                ref2va_model,
                text_encoder,
                video_vae,
                image_vae,
                image_analyzer,
                prompt_writer,
            )
        except Exception as exc:
            emit(
                "v6.loader.error",
                memory=True,
                elapsed_s=time.perf_counter() - started,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise
        emit(
            "v6.loader.end",
            memory=True,
            elapsed_s=time.perf_counter() - started,
            bundle_id=id(result[0]),
            clip_id=id(result[1]),
            vae_id=id(result[2]),
        )
        return result


class H3StudioNativeSamplingPreset(H3StudioContextSamplingPreset):
    """Keep the selected acceleration recipe and preserve native Comfy residency."""

    def build(self, model, studio_context):
        from .acceleration import LIGHTX_PROFILES, PDD_PROFILES, is_pdd_profile

        profile = str(studio_context.state.generation.sampling_profile)
        seed = int(getattr(studio_context.state.generation, "seed", 0))
        custom_specs = normalize_custom_loras(dict(studio_context.state.ui).get("custom_loras", ()))
        accelerated = profile in LIGHTX_PROFILES or is_pdd_profile(profile)
        started = time.perf_counter()
        emit(
            "v6.sampler.build.begin",
            memory=True,
            profile=profile,
            seed=seed,
            accelerated=accelerated,
            custom_loras=len(custom_specs),
            input_patcher_id=id(model),
        )

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
        if policy.keep_diffusion_hot:
            _remove_sampling_release(built_model)
            handoff = "keep-hot"
        else:
            handoff = attach_sampling_stage_release(built_model)

        step_count = max(0, len(sigmas) - 1) if hasattr(sigmas, "__len__") else -1
        info = (
            f"{info} | sampling_residency=native-comfy-manager | post_sample={handoff} | "
            f"policy={policy.label} | seed={seed}"
        )
        emit(
            "v6.sampler.build.end",
            memory=True,
            elapsed_s=time.perf_counter() - started,
            profile=profile,
            seed=seed,
            steps=step_count,
            policy=policy.label,
            post_sample=handoff,
            output_patcher_id=id(built_model),
            model_id=id(getattr(built_model, "model", built_model)),
        )
        return built_model, sampler, sigmas, info


class H3StudioNativeDecode(H3StudioDecode):
    """Exact native H3 decode, then release only the final VAE on normal VRAM."""

    def decode(self, samples, vae):
        policy = hardware_policy()
        started = time.perf_counter()
        emit(
            "v6.decode.begin",
            memory=True,
            policy=policy.label,
            vae_id=id(vae),
            vae_patcher_id=id(getattr(vae, "patcher", vae)),
        )
        try:
            result = H3StudioDecode.decode(self, samples, vae)
        except Exception as exc:
            emit(
                "v6.decode.error",
                memory=True,
                elapsed_s=time.perf_counter() - started,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise

        release = "kept-hot"
        release_elapsed = 0.0
        if not policy.keep_all_hot:
            release_started = time.perf_counter()
            release = release_stage_patcher(getattr(vae, "patcher", None), label="final_vae").mode
            release_elapsed = time.perf_counter() - release_started

        images, decoded_frames, info, recommended_index = result
        total_elapsed = time.perf_counter() - started
        info = (
            f"{info} Native-v6 policy={policy.label}; final_vae={release}; "
            f"stage={total_elapsed:.3f}s."
        )
        emit(
            "v6.decode.end",
            memory=True,
            elapsed_s=total_elapsed,
            release_s=release_elapsed,
            policy=policy.label,
            final_vae=release,
            decoded_frames=decoded_frames,
            recommended_index=recommended_index,
        )
        return images, decoded_frames, info, recommended_index


def install_native_max_speed_runtime() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    started = time.perf_counter()
    emit("v6.runtime.install.begin", memory=True, version="v6")
    _configure_comfy_for_speed()
    _install_native_conditioning_guard()
    _INSTALLED = True
    emit(
        "v6.runtime.install.end",
        memory=True,
        elapsed_s=time.perf_counter() - started,
        startup_model_io=False,
        background_threads=0,
        component_monkeypatch_cache=False,
    )


__all__ = [
    "H3StudioNativeDecode",
    "H3StudioNativeLoader",
    "H3StudioNativeSamplingPreset",
    "HardwarePolicy",
    "hardware_policy",
    "install_native_max_speed_runtime",
]
