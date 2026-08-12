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

import hashlib
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
from .runtime_trace import emit, span

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


def _key_digest(value: Any) -> str:
    return hashlib.sha1(repr(value).encode("utf-8", errors="replace")).hexdigest()[:12]


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

    policy = HardwarePolicy(
        total_vram=total_vram,
        total_ram=total_ram,
        keep_diffusion_for_vae=total_vram >= KEEP_DIFFUSION_FOR_VAE,
        keep_all_hot=total_vram >= KEEP_ALL_HOT,
        low_host_ram=bool(total_ram and total_ram <= LOW_HOST_RAM),
    )
    emit(
        "policy.detected",
        memory=True,
        policy=policy.label,
        total_vram_gib=policy.total_vram / GIB,
        total_ram_gib=policy.total_ram / GIB,
        keep_diffusion_for_vae=policy.keep_diffusion_for_vae,
        keep_all_hot=policy.keep_all_hot,
        low_host_ram=policy.low_host_ram,
    )
    return policy


def _configure_comfy_for_speed() -> None:
    """Restore the known-fast low-RAM DynamicVRAM policy without forcing it elsewhere."""

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
                "[H3 Studio] Max-speed policy: low host RAM %.1f GiB -> ComfyUI fast-disk enabled for DynamicVRAM",
                policy.total_ram / GIB,
            )
        if args is not None:
            fast_disk_after = bool(getattr(args, "fast_disk", False))
    except Exception as exc:
        LOGGER.debug("[H3 Studio] fast-disk auto policy unavailable: %s", exc)
        emit("policy.fast_disk.error", error_type=type(exc).__name__, error=str(exc))

    emit(
        "policy.configured",
        memory=True,
        models=True,
        policy=policy.label,
        fast_disk_before=fast_disk_before,
        fast_disk_after=fast_disk_after,
        high_ram=high_ram,
        auto_fast_disk_disabled=_env_flag("H3STUDIO_DISABLE_AUTO_FAST_DISK"),
    )


def _cached_clip(name: str):
    key = str(name)
    with _CLIP_LOCK:
        cached = _CLIP_CACHE.get(key)
        if cached is not None:
            emit("component.cache.hit", component="text_encoder", name=key, object_id=id(cached))
            return cached
        with span("component.load", memory=True, models=True, component="text_encoder", name=key) as trace:
            value = _ORIGINAL_LOAD_CLIP(name)
            _CLIP_CACHE[key] = value
            trace["object_id"] = id(value)
            trace["patcher_id"] = id(getattr(value, "patcher", value))
            return value


def _cached_vae(name: str):
    key = str(name)
    with _VAE_LOCK:
        cached = _VAE_CACHE.get(key)
        if cached is not None:
            emit("component.cache.hit", component="video_vae", name=key, object_id=id(cached))
            return cached
        with span("component.load", memory=True, models=True, component="video_vae", name=key) as trace:
            value = _ORIGINAL_LOAD_VAE(name)
            _VAE_CACHE[key] = value
            trace["object_id"] = id(value)
            trace["patcher_id"] = id(getattr(value, "patcher", value))
            return value


def _cached_unet(name: str):
    key = str(name)
    with _UNET_LOCK:
        cached = _UNET_CACHE.get(key)
        if cached is not None:
            emit("component.cache.hit", component="transformer", name=key, patcher_id=id(cached))
            return cached
        with span("component.load", memory=True, models=True, component="transformer", name=key) as trace:
            value = _ORIGINAL_LOAD_UNET(name)
            _UNET_CACHE[key] = value
            trace["patcher_id"] = id(value)
            trace["model_id"] = id(getattr(value, "model", value))
            return value


def _install_component_caches() -> None:
    loader_module._load_clip = _cached_clip
    loader_module._load_vae = _cached_vae
    loader_module._load_unet = _cached_unet
    emit("component.cache.install", clip=True, vae=True, transformer=True)


def _install_conditioning_fastpath() -> None:
    """One TE load owner, zero warm-hit work, no explicit sync/cache flushes."""

    from . import conditioning_cache

    current = conditioning_cache._encode_prompt
    if bool(getattr(current, "__h3studio_max_speed_v5__", False)):
        emit("conditioning.fastpath.install", result="already-installed")
        return

    def encode_prompt(bundle: Any, key: Any, build_tokens):
        key_hash = _key_digest(key)
        cached = conditioning_cache._PROMPT_CACHE.get(key)
        if cached is not None:
            emit(
                "conditioning.cache.hit",
                memory=True,
                models=True,
                key=key_hash,
                clip=getattr(bundle, "clip_name", "unknown"),
                model_management="zero",
            )
            return cached, "HIT", 0.0, "max-speed-v5; cache=hit; model_management=zero"

        policy = hardware_policy()
        started = time.perf_counter()
        emit(
            "conditioning.cache.miss",
            memory=True,
            models=True,
            key=key_hash,
            clip=getattr(bundle, "clip_name", "unknown"),
            policy=policy.label,
        )
        diffusion_release = "kept-hot"
        if not policy.keep_all_hot:
            release_started = time.perf_counter()
            result = release_stage_patcher(getattr(bundle, "_model", None), label="pre_text_diffusion")
            diffusion_release = result.mode
            emit(
                "conditioning.pre_text_handoff",
                memory=True,
                models=True,
                key=key_hash,
                mode=result.mode,
                elapsed_s=time.perf_counter() - release_started,
                loaded_before_gib=result.loaded_before / GIB,
                loaded_after_gib=result.loaded_after / GIB,
            )

        tokenize_started = time.perf_counter()
        tokens = build_tokens()
        tokenized = time.perf_counter()
        emit(
            "conditioning.tokenize.end",
            key=key_hash,
            elapsed_s=tokenized - tokenize_started,
        )

        encode_started = time.perf_counter()
        emit("conditioning.encode.begin", memory=True, models=True, key=key_hash, policy=policy.label)
        conditioning = bundle.clip.encode_from_tokens_scheduled(tokens)
        encoded = time.perf_counter()
        emit(
            "conditioning.encode.end",
            memory=True,
            models=True,
            key=key_hash,
            elapsed_s=encoded - encode_started,
        )

        text_release = "kept-hot"
        if not policy.keep_all_hot:
            release_started = time.perf_counter()
            patcher = getattr(bundle.clip, "patcher", None)
            release = release_stage_patcher(patcher, label="text_encoder")
            text_release = release.mode
            emit(
                "conditioning.text_handoff",
                memory=True,
                models=True,
                key=key_hash,
                mode=release.mode,
                elapsed_s=time.perf_counter() - release_started,
                loaded_before_gib=release.loaded_before / GIB,
                loaded_after_gib=release.loaded_after / GIB,
            )

        conditioning_cache._PROMPT_CACHE.put(key, conditioning)
        finished = time.perf_counter()
        runtime = (
            "max-speed-v5; single-scheduled-text-encode; "
            f"tokenize={tokenized - tokenize_started:.3f}s; encode={encoded - encode_started:.3f}s; "
            f"post={finished - encoded:.3f}s; diffusion={diffusion_release}; text_encoder={text_release}; "
            f"policy={policy.label}"
        )
        emit(
            "conditioning.miss.complete",
            memory=True,
            models=True,
            key=key_hash,
            elapsed_s=finished - started,
            tokenize_s=tokenized - tokenize_started,
            encode_s=encoded - encode_started,
            post_s=finished - encoded,
            diffusion_handoff=diffusion_release,
            text_handoff=text_release,
            policy=policy.label,
        )
        return conditioning, "MISS", finished - started, runtime

    encode_prompt.__h3studio_max_speed_v5__ = True
    conditioning_cache._encode_prompt = encode_prompt
    emit("conditioning.fastpath.install", result="installed")


def _remove_sampling_release(model: Any) -> None:
    try:
        import comfy.patcher_extension

        model.remove_wrappers_with_key(comfy.patcher_extension.WrappersMP.OUTER_SAMPLE, POST_SAMPLE_RELEASE_KEY)
        emit("sampler.post_release.remove", patcher_id=id(model), result="removed-or-absent")
    except Exception as exc:
        emit("sampler.post_release.remove", patcher_id=id(model), result="unavailable", error_type=type(exc).__name__)


def _remove_force_full_experiment(model: Any) -> None:
    try:
        import comfy.patcher_extension

        from .runtime_stability import SAMPLING_RESIDENCY_WRAPPER_KEY

        model.remove_wrappers_with_key(
            comfy.patcher_extension.WrappersMP.PREPARE_SAMPLING,
            SAMPLING_RESIDENCY_WRAPPER_KEY,
        )
        emit("sampler.force_full_wrapper.remove", patcher_id=id(model), result="removed-or-absent")
    except Exception as exc:
        emit("sampler.force_full_wrapper.remove", patcher_id=id(model), result="unavailable", error_type=type(exc).__name__)


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
        key_hash = _key_digest(key)
        with _LOADER_CACHE_LOCK:
            if key == _LOADER_CACHE_KEY and _LOADER_CACHE_VALUE is not None:
                emit(
                    "bundle.cache.hit",
                    memory=True,
                    models=True,
                    key=key_hash,
                    bundle_id=id(_LOADER_CACHE_VALUE[0]),
                )
                return _LOADER_CACHE_VALUE
            with span(
                "bundle.load",
                memory=True,
                models=True,
                key=key_hash,
                fl2va=fl2va_model,
                ref2va=ref2va_model,
                text_encoder=text_encoder,
                video_vae=video_vae,
            ) as trace:
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
                trace["bundle_id"] = id(value[0])
                trace["clip_id"] = id(value[1])
                trace["vae_id"] = id(value[2])
                return value


class H3StudioMaxSpeedSamplingPreset(H3StudioContextSamplingPreset):
    """Preserve all acceleration/custom-LoRA behavior and let native Comfy own residency."""

    def build(self, model, studio_context):
        from .acceleration import LIGHTX_PROFILES, PDD_PROFILES, is_pdd_profile

        profile = str(studio_context.state.generation.sampling_profile)
        seed = int(getattr(studio_context.state.generation, "seed", 0))
        custom_specs = normalize_custom_loras(dict(studio_context.state.ui).get("custom_loras", ()))
        accelerated = profile in LIGHTX_PROFILES or is_pdd_profile(profile)
        emit(
            "sampler.build.begin",
            memory=True,
            models=True,
            profile=profile,
            seed=seed,
            accelerated=accelerated,
            custom_loras=len(custom_specs),
            input_patcher_id=id(model),
        )
        started = time.perf_counter()
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

        step_count = max(0, len(sigmas) - 1) if hasattr(sigmas, "__len__") else -1
        info = (
            f"{info} | sampling_residency=native-comfy-manager | post_sample={handoff} | "
            f"policy={policy.label} | seed={seed}"
        )
        emit(
            "sampler.build.end",
            memory=True,
            models=True,
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


class H3StudioMaxSpeedDecode(H3StudioDecode):
    """Use exact native H3 VAE decode and keep only useful residency afterward."""

    def decode(self, samples, vae):
        policy = hardware_policy()
        started = time.perf_counter()
        emit(
            "decode.begin",
            memory=True,
            models=True,
            policy=policy.label,
            vae_id=id(vae),
            vae_patcher_id=id(getattr(vae, "patcher", vae)),
        )
        try:
            result = H3StudioDecode.decode(self, samples, vae)
        except Exception as exc:
            emit(
                "decode.error",
                memory=True,
                models=True,
                elapsed_s=time.perf_counter() - started,
                policy=policy.label,
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
            f"{info} Max-speed policy={policy.label}; final_vae={release}; "
            f"stage={total_elapsed:.3f}s."
        )
        emit(
            "decode.end",
            memory=True,
            models=True,
            elapsed_s=total_elapsed,
            release_s=release_elapsed,
            policy=policy.label,
            final_vae=release,
            decoded_frames=decoded_frames,
            recommended_index=recommended_index,
        )
        return images, decoded_frames, info, recommended_index


def start_component_prewarm() -> str:
    """Hide first-click CLIP/VAE construction behind server idle time."""

    global _PREWARM_STARTED, _PREWARM_ERROR
    if _env_flag("H3STUDIO_DISABLE_STARTUP_PREWARM"):
        emit("prewarm.skip", reason="disabled-by-env")
        return "disabled-by-env"

    with _PREWARM_LOCK:
        if _PREWARM_STARTED:
            emit("prewarm.skip", reason="already-started")
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
                    emit("prewarm.skip", reason="missing-component-choice", clip_choices=len(clips), vae_choices=len(vaes))
                    return
                clip_name = _resolve_text_encoder(clips[0])
                vae_name = vaes[0]
                emit(
                    "prewarm.begin",
                    memory=True,
                    models=True,
                    clip=clip_name,
                    vae=vae_name,
                    diffusion="lazy",
                )
                clip = _cached_clip(clip_name)
                vae = _cached_vae(vae_name)

                policy = hardware_policy()
                gpu_prewarm = policy.keep_all_hot and not _env_flag("H3STUDIO_DISABLE_GPU_PREWARM")
                if gpu_prewarm:
                    import comfy.model_management as mm

                    patchers = [
                        patcher
                        for patcher in (getattr(clip, "patcher", None), getattr(vae, "patcher", None))
                        if patcher is not None
                    ]
                    if patchers:
                        gpu_started = time.perf_counter()
                        emit("prewarm.gpu.begin", memory=True, models=True, patchers=len(patchers))
                        mm.load_models_gpu(patchers, force_full_load=True)
                        emit(
                            "prewarm.gpu.end",
                            memory=True,
                            models=True,
                            elapsed_s=time.perf_counter() - gpu_started,
                            patchers=len(patchers),
                        )
            except Exception as exc:
                _PREWARM_ERROR = f"{type(exc).__name__}: {exc}"
                LOGGER.warning("[H3 Studio] Background prewarm failed nonfatally: %s", _PREWARM_ERROR)
                emit(
                    "prewarm.error",
                    memory=True,
                    models=True,
                    elapsed_s=time.perf_counter() - started,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            finally:
                _PREWARM_DONE.set()
                emit(
                    "prewarm.end",
                    memory=True,
                    models=True,
                    elapsed_s=time.perf_counter() - started,
                    error=_PREWARM_ERROR or "none",
                )

        threading.Thread(target=worker, name="H3StudioMaxSpeedPrewarm", daemon=True).start()
        emit("prewarm.thread.start", thread="H3StudioMaxSpeedPrewarm")
        return "background-started"


def install_max_speed_runtime() -> None:
    global _INSTALLED
    if _INSTALLED:
        emit("runtime.install", result="already-installed")
        return
    emit("runtime.install.begin", memory=True, models=True, version="v5")
    started = time.perf_counter()
    _configure_comfy_for_speed()
    _install_component_caches()
    _install_conditioning_fastpath()
    _INSTALLED = True
    emit(
        "runtime.install.end",
        memory=True,
        models=True,
        version="v5",
        elapsed_s=time.perf_counter() - started,
    )


__all__ = [
    "H3StudioMaxSpeedDecode",
    "H3StudioMaxSpeedLoader",
    "H3StudioMaxSpeedSamplingPreset",
    "HardwarePolicy",
    "hardware_policy",
    "install_max_speed_runtime",
    "start_component_prewarm",
]
