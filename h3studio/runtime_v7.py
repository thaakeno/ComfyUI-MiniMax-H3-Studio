"""Final native-first throughput policy for MiniMax H3 Studio v7.

v7 is based directly on the measured L4 failures rather than synthetic loader
benchmarks.  The critical rules are:

* H3 Studio NEVER silently enables ComfyUI ``fast_disk``.  That option is for
  genuinely fast local NVMe; on the Lightning persistent model store it makes
  AIMDO stream mmap-backed weights from disk during every dynamic layer fault
  and turned the 32B text encoder from ~20-50 s into 100-180 s.
* The native Comfy scheduled text encode remains the only text-model load owner.
* After a text miss, the existing manager stage handoff unloads the completed
  text encoder.  v7 then performs only a conservative inactive-pin pressure
  trim when host RAM is actually low.  It never flushes active H3 diffusion
  pins on a warm cache hit.
* Exact prompt cache hits perform zero text-model/model-manager work.
* 20 GiB+ GPUs keep diffusion hot across seed-only reruns; lower-VRAM hardware
  uses manager stage handoffs; 40 GiB+ hardware may keep all major stages hot.
* No model is constructed, read, or moved merely because ComfyUI started.

Sampler math, quantization, LightX settings and native H3 VAE semantics are not
changed by this module.
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
KEEP_DIFFUSION_HOT = 20 * GIB
KEEP_ALL_HOT = 40 * GIB
HOST_PRESSURE_HEADROOM = 8 * GIB
HOST_PRESSURE_HYSTERESIS = 512 * 1024**2
_INSTALLED = False


def _key_digest(value: Any) -> str:
    return hashlib.sha1(repr(value).encode("utf-8", errors="replace")).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class HardwarePolicy:
    total_vram: int
    total_ram: int
    keep_diffusion_hot: bool
    keep_all_hot: bool

    @property
    def label(self) -> str:
        if self.keep_all_hot:
            return "resident-high-vram"
        if self.keep_diffusion_hot:
            return "hot-diffusion-native-pinned-host"
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

        total_vram = int(mm.get_total_memory(mm.get_torch_device()))
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
    )
    emit(
        "v7.policy.detected",
        memory=True,
        policy=policy.label,
        total_vram_gib=policy.total_vram / GIB,
        total_ram_gib=policy.total_ram / GIB,
        keep_diffusion_hot=policy.keep_diffusion_hot,
        keep_all_hot=policy.keep_all_hot,
    )
    return policy


def _configure_comfy_for_speed() -> None:
    """Observe Comfy memory options but do not rewrite them behind the user."""

    policy = hardware_policy()
    fast_disk = False
    high_ram = False
    disable_pinned = False
    try:
        import comfy.model_management as mm

        args = getattr(mm, "args", None)
        if args is not None:
            fast_disk = bool(getattr(args, "fast_disk", False))
            high_ram = bool(getattr(args, "high_ram", False))
            disable_pinned = bool(getattr(args, "disable_pinned_memory", False))
    except Exception as exc:
        emit("v7.policy.inspect.error", error_type=type(exc).__name__, error=str(exc))

    if fast_disk:
        LOGGER.warning(
            "[H3 Studio] ComfyUI --fast-disk is enabled externally. H3 Studio v7 does not enable it; "
            "on non-NVMe/network-backed model storage this can make DynamicVRAM dramatically slower."
        )

    emit(
        "v7.policy.configured",
        memory=True,
        policy=policy.label,
        fast_disk=fast_disk,
        fast_disk_mutated_by_studio=False,
        high_ram=high_ram,
        pinned_memory_disabled=disable_pinned,
        startup_model_io=False,
        background_threads=0,
    )


def _model_source(category: str, name: str) -> dict[str, Any]:
    """Return cheap path facts so a slow network/symlink source is obvious in logs."""

    try:
        import folder_paths

        path = folder_paths.get_full_path(category, name)
        if not path:
            return {"category": category, "name": name, "path": "missing"}
        real = os.path.realpath(path)
        size = os.path.getsize(real)
        return {
            "category": category,
            "name": name,
            "path": path,
            "realpath": real,
            "symlink": os.path.islink(path),
            "real_tmpfs": real.startswith("/dev/shm/"),
            "size_gib": size / GIB,
        }
    except Exception as exc:
        return {
            "category": category,
            "name": name,
            "path_error": type(exc).__name__,
        }


def _emit_model_sources(fl2va_model: str, ref2va_model: str, text_encoder: str, video_vae: str) -> None:
    for category, name, role in (
        ("diffusion_models", fl2va_model, "fl2va"),
        ("diffusion_models", ref2va_model, "ref2va"),
        ("text_encoders", text_encoder, "text_encoder"),
        ("vae", video_vae, "video_vae"),
    ):
        emit("v7.model_source", role=role, **_model_source(category, name))


def _trim_inactive_pins_if_pressured(*, stage: str) -> None:
    """Keep a small RAM safety margin without evicting the active hot model.

    Comfy's non-fast-disk DynamicVRAM path already performs RAM-aware pin
    balancing.  This is only a stage-boundary backstop for 32 GiB hosts.  It
    asks Comfy to free *inactive* pins only; active diffusion residency is never
    sacrificed here.
    """

    try:
        import psutil
        import comfy.model_management as mm

        available_before = int(psutil.virtual_memory().available)
        pinned_before = int(getattr(mm, "TOTAL_PINNED_MEMORY", 0))
        shortfall = HOST_PRESSURE_HEADROOM - available_before
        if shortfall <= 0:
            emit(
                "v7.host_pins.ok",
                memory=True,
                stage=stage,
                pinned_gib=pinned_before / GIB,
                headroom_target_gib=HOST_PRESSURE_HEADROOM / GIB,
            )
            return

        free_pins = getattr(mm, "free_pins", None)
        if not callable(free_pins):
            emit(
                "v7.host_pins.trim.skip",
                memory=True,
                stage=stage,
                reason="manager_api_missing",
                shortfall_gib=shortfall / GIB,
            )
            return

        started = time.perf_counter()
        # evict_active=False is intentional.  The completed TE manager handoff
        # should already have made its pins disposable; a hot diffusion model is
        # protected even if the host is under pressure.
        freed = int(free_pins(shortfall + HOST_PRESSURE_HYSTERESIS, evict_active=False) or 0)
        available_after = int(psutil.virtual_memory().available)
        pinned_after = int(getattr(mm, "TOTAL_PINNED_MEMORY", 0))
        emit(
            "v7.host_pins.trim",
            memory=True,
            stage=stage,
            elapsed_s=time.perf_counter() - started,
            requested_gib=(shortfall + HOST_PRESSURE_HYSTERESIS) / GIB,
            freed_gib=freed / GIB,
            pinned_before_gib=pinned_before / GIB,
            pinned_after_gib=pinned_after / GIB,
            available_before_gib=available_before / GIB,
            available_after_gib=available_after / GIB,
        )
    except Exception as exc:
        emit(
            "v7.host_pins.trim.error",
            stage=stage,
            error_type=type(exc).__name__,
            error=str(exc),
        )


def _install_native_conditioning_guard() -> None:
    """One native text-encode owner; exact hits stay completely hot."""

    from . import conditioning_cache

    current = conditioning_cache._encode_prompt
    if bool(getattr(current, "__h3studio_native_v7__", False)):
        return
    native_encode = current

    def encode_prompt(bundle: Any, key: Any, build_tokens):
        key_hash = _key_digest(key)
        cached = conditioning_cache._PROMPT_CACHE.get(key)
        if cached is not None:
            emit(
                "v7.conditioning.hit",
                memory=True,
                key=key_hash,
                model_management="zero",
            )
            return cached, "HIT", 0.0, "native-v7; cache=hit; model_management=zero"

        policy = hardware_policy()
        started = time.perf_counter()
        diffusion = getattr(bundle, "_model", None)
        diffusion_handoff = "not-loaded"
        if diffusion is not None and not policy.keep_all_hot:
            release_started = time.perf_counter()
            release = release_stage_patcher(diffusion, label="pre_text_diffusion")
            diffusion_handoff = release.mode
            emit(
                "v7.conditioning.pre_text_diffusion",
                memory=True,
                key=key_hash,
                elapsed_s=time.perf_counter() - release_started,
                mode=release.mode,
                loaded_before_gib=release.loaded_before / GIB,
                loaded_after_gib=release.loaded_after / GIB,
            )

        emit(
            "v7.conditioning.native_encode.begin",
            memory=True,
            key=key_hash,
            policy=policy.label,
            diffusion_handoff=diffusion_handoff,
        )
        result = native_encode(bundle, key, build_tokens)
        encode_elapsed = time.perf_counter() - started
        emit(
            "v7.conditioning.native_encode.end",
            memory=True,
            key=key_hash,
            elapsed_s=encode_elapsed,
            cache_state=result[1],
            native_runtime=result[3],
            policy=policy.label,
        )

        # native_encode's MISS path already performs the targeted text-encoder
        # manager handoff.  Only after that handoff do we consider inactive host
        # pin trimming.
        if result[1] == "MISS" and not policy.keep_all_hot:
            _trim_inactive_pins_if_pressured(stage="after_text_encoder")
        return result

    encode_prompt.__h3studio_native_v7__ = True
    conditioning_cache._encode_prompt = encode_prompt
    emit("v7.conditioning.install", result="native-wrapper-installed")


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


class H3StudioNativeLoaderV7(H3StudioLoader):
    """Native on-demand H3 loader with source/timing telemetry only."""

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
        _emit_model_sources(fl2va_model, ref2va_model, text_encoder, video_vae)
        emit(
            "v7.loader.begin",
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
                "v7.loader.error",
                memory=True,
                elapsed_s=time.perf_counter() - started,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise
        emit(
            "v7.loader.end",
            memory=True,
            elapsed_s=time.perf_counter() - started,
            bundle_id=id(result[0]),
            clip_id=id(result[1]),
            vae_id=id(result[2]),
        )
        return result


class H3StudioNativeSamplingPresetV7(H3StudioContextSamplingPreset):
    """Preserve acceleration/custom LoRAs while native Comfy owns residency."""

    def build(self, model, studio_context):
        from .acceleration import LIGHTX_PROFILES, PDD_PROFILES, is_pdd_profile

        profile = str(studio_context.state.generation.sampling_profile)
        seed = int(getattr(studio_context.state.generation, "seed", 0))
        custom_specs = normalize_custom_loras(dict(studio_context.state.ui).get("custom_loras", ()))
        accelerated = profile in LIGHTX_PROFILES or is_pdd_profile(profile)
        started = time.perf_counter()
        emit(
            "v7.sampler.build.begin",
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
            "v7.sampler.build.end",
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


class H3StudioNativeDecodeV7(H3StudioDecode):
    """Exact native H3 decode, then release only final VAE on normal VRAM."""

    def decode(self, samples, vae):
        policy = hardware_policy()
        started = time.perf_counter()
        emit(
            "v7.decode.begin",
            memory=True,
            policy=policy.label,
            vae_id=id(vae),
            vae_patcher_id=id(getattr(vae, "patcher", vae)),
        )
        try:
            result = H3StudioDecode.decode(self, samples, vae)
        except Exception as exc:
            emit(
                "v7.decode.error",
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
            _trim_inactive_pins_if_pressured(stage="after_final_vae")

        images, decoded_frames, info, recommended_index = result
        total_elapsed = time.perf_counter() - started
        info = (
            f"{info} Native-v7 policy={policy.label}; final_vae={release}; "
            f"stage={total_elapsed:.3f}s."
        )
        emit(
            "v7.decode.end",
            memory=True,
            elapsed_s=total_elapsed,
            release_s=release_elapsed,
            policy=policy.label,
            final_vae=release,
            decoded_frames=decoded_frames,
            recommended_index=recommended_index,
        )
        return images, decoded_frames, info, recommended_index


def install_native_max_speed_runtime_v7() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    started = time.perf_counter()
    emit("v7.runtime.install.begin", memory=True, version="v7")
    _configure_comfy_for_speed()
    _install_native_conditioning_guard()
    _INSTALLED = True
    emit(
        "v7.runtime.install.end",
        memory=True,
        elapsed_s=time.perf_counter() - started,
        startup_model_io=False,
        background_threads=0,
        component_monkeypatch_cache=False,
        fast_disk_mutated_by_studio=False,
    )


__all__ = [
    "GIB",
    "H3StudioNativeDecodeV7",
    "H3StudioNativeLoaderV7",
    "H3StudioNativeSamplingPresetV7",
    "HardwarePolicy",
    "hardware_policy",
    "install_native_max_speed_runtime_v7",
]
