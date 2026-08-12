"""Runtime stability policy for memory-constrained MiniMax H3 sessions.

The expensive H3 stages remain owned by ComfyUI's native model manager. Studio
uses targeted manager-level handoffs only after a stage has finished, removing
the dynamic-on-dynamic residency overlap that can make sequential H3 stages
stream unpredictably on 22 GiB / 32 GiB systems.
"""

from __future__ import annotations

import logging
import os

from .runtime_handoff import attach_sampling_stage_release, release_stage_patcher

LOGGER = logging.getLogger(__name__)
GIB = 1024**3
LOW_RAM_THRESHOLD = 48 * GIB
SAMPLING_RESIDENCY_WRAPPER_KEY = "h3studio_sampling_residency"
_INSTALLED = False
_RUNTIME_NODE_CLASSES: tuple[type, type] | None = None


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def configure_low_ram_fast_disk() -> str:
    """Enable ComfyUI's disk-backed DynamicVRAM path on small host-RAM systems."""

    if _env_flag("H3STUDIO_DISABLE_AUTO_FAST_DISK"):
        return "disabled-by-env"
    try:
        import comfy.model_management as mm
        import psutil

        total_ram = int(psutil.virtual_memory().total)
        args = getattr(mm, "args", None)
        if args is None:
            return "unavailable"
        if total_ram > LOW_RAM_THRESHOLD:
            return "not-needed"
        if bool(getattr(args, "high_ram", False)):
            return "high-ram-mode"
        if bool(getattr(args, "fast_disk", False)):
            return "already-enabled"
        args.fast_disk = True
        LOGGER.warning(
            "[H3 Studio] Low host RAM detected (%.1f GiB): enabled ComfyUI --fast-disk behavior for DynamicVRAM. "
            "This reduces duplicate host-weight buffering; real model files in /dev/shm should still be moved "
            "to persistent storage.",
            total_ram / GIB,
        )
        return "enabled"
    except Exception as exc:
        LOGGER.debug("[H3 Studio] Automatic fast-disk setup skipped: %s", exc)
        return "unavailable"


def accelerated_preview_steps(total_steps: int) -> frozenset[int]:
    """Compatibility helper: accelerated runs no longer suppress requested previews."""

    return frozenset(range(max(0, int(total_steps))))


def _install_conditioning_diagnostics() -> bool:
    """Observe cache misses around the native CLIP encode without preloading it."""

    try:
        from . import conditioning_cache
        from .runtime_diagnostics import runtime_snapshot
    except Exception as exc:
        LOGGER.debug("[H3 Studio Runtime] Conditioning diagnostics unavailable: %s", exc)
        return False

    original = conditioning_cache._encode_prompt
    if bool(getattr(original, "__h3studio_runtime_diagnostics__", False)):
        return True

    def diagnosed_encode(bundle, key, build_tokens):
        # Preserve the zero-work cache-hit path: checking the same bounded cache
        # here avoids adding psutil/CUDA queries to unchanged-prompt reruns.
        cached = conditioning_cache._PROMPT_CACHE.get(key)
        if cached is not None:
            return cached, "HIT", 0.0, "warm-cache"

        import time

        patcher = getattr(getattr(bundle, "clip", None), "patcher", None)
        before = runtime_snapshot("conditioning.encode_request.before", patcher=patcher)
        started = time.perf_counter()
        result = original(bundle, key, build_tokens)
        runtime_snapshot(
            "conditioning.encode_request.after",
            patcher=patcher,
            previous=before,
            elapsed=time.perf_counter() - started,
            detail=f"cache={result[1]} {result[3]}",
        )
        return result

    diagnosed_encode.__h3studio_runtime_diagnostics__ = True
    conditioning_cache._encode_prompt = diagnosed_encode
    return True


def _log_comfy_runtime_identity() -> None:
    try:
        import comfy

        path = str(getattr(comfy, "__file__", "unknown"))
        version = str(getattr(comfy, "__version__", "unknown"))
        LOGGER.info("[H3 Studio] Active ComfyUI import | version=%s | path=%s", version, path)
    except Exception as exc:
        LOGGER.debug("[H3 Studio] Could not report ComfyUI import identity: %s", exc)


def _remove_experimental_sampling_residency(model: object) -> bool:
    """Remove Studio's old force-full PREPARE_SAMPLING experiment."""

    try:
        import comfy.patcher_extension

        model.remove_wrappers_with_key(
            comfy.patcher_extension.WrappersMP.PREPARE_SAMPLING,
            SAMPLING_RESIDENCY_WRAPPER_KEY,
        )
        return True
    except Exception:
        return False


def runtime_node_classes() -> tuple[type, type]:
    """Build Comfy-facing node subclasses lazily at actual ComfyUI import time."""

    global _RUNTIME_NODE_CLASSES
    if _RUNTIME_NODE_CLASSES is not None:
        return _RUNTIME_NODE_CLASSES

    from .nodes.image_runtime import H3StudioDecode
    from .nodes.performance import H3StudioFastDecode, H3StudioOptimizedContextSamplingPreset
    from .runtime_diagnostics import attach_sampling_diagnostics, runtime_snapshot

    class H3StudioStableContextSamplingPreset(H3StudioOptimizedContextSamplingPreset):
        """Keep acceleration/LoRA caching while leaving model loading to ComfyUI."""

        def build(self, model, studio_context):
            import time

            before = runtime_snapshot("sampling_profile.before", patcher=model)
            started = time.perf_counter()
            built_model, sampler, sigmas, info = super().build(model, studio_context)
            runtime_snapshot(
                "sampling_profile.after",
                patcher=built_model,
                previous=before,
                elapsed=time.perf_counter() - started,
            )
            if not _env_flag("H3STUDIO_EXPERIMENTAL_FULL_DIFFUSION"):
                _remove_experimental_sampling_residency(built_model)
                info = f"{info} | sampling_residency=native-comfy-manager"
                LOGGER.info("[H3 Studio] Sampling residency restored to native ComfyUI manager")

            handoff = attach_sampling_stage_release(built_model)
            diagnostics = attach_sampling_diagnostics(built_model)
            info = f"{info} | sampling_handoff={handoff} | runtime_diagnostics={diagnostics}"
            return built_model, sampler, sigmas, info

    class H3StudioStableDecode(H3StudioFastDecode):
        """Exact H3 decode with native chunked I/O and a clean final handoff."""

        def decode(self, samples, vae):
            import time

            first_stage = getattr(vae, "first_stage_model", None)
            chunked = bool(getattr(first_stage, "comfy_has_chunked_io", False))
            patcher = getattr(vae, "patcher", None)
            before = runtime_snapshot("vae_decode.before", patcher=patcher)
            started = time.perf_counter()
            manager_path = "native-comfy-chunked" if chunked else "legacy-full-stage-fallback"
            release = None

            try:
                if chunked:
                    # Current Comfy H3 streams spatial/temporal chunks into a
                    # preallocated output. Do not set disable_offload here.
                    result = H3StudioDecode.decode(self, samples, vae)
                else:
                    LOGGER.warning(
                        "[H3 Studio] This ComfyUI core lacks MiniMax H3 chunked VAE I/O. Exact decode can become "
                        "extremely slow or memory-heavy. Update ComfyUI to a build containing the H3 chunked-I/O "
                        "changes before judging decode performance."
                    )
                    result = super().decode(samples, vae)
            finally:
                # The next prompt's 32B encoder should never inherit final-VAE
                # residency. This is a targeted Comfy manager unload, not a
                # ModelPatcher partial-unload hack.
                release = release_stage_patcher(patcher, label="final_vae")
                elapsed = time.perf_counter() - started
                runtime_snapshot(
                    "vae_decode.after",
                    patcher=patcher,
                    previous=before,
                    elapsed=elapsed,
                    detail=f"path={manager_path} | {release.summary()}",
                )

            images, decoded_frames, info, recommended_index = result
            info = f"{info} VAE manager path: {manager_path}. {release.summary()}."
            return images, decoded_frames, info, recommended_index

    _RUNTIME_NODE_CLASSES = H3StudioStableContextSamplingPreset, H3StudioStableDecode
    return _RUNTIME_NODE_CLASSES


def install_runtime_stability() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    configure_low_ram_fast_disk()
    _log_comfy_runtime_identity()
    _install_conditioning_diagnostics()
