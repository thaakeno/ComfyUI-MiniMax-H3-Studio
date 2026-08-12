"""Adaptive VAE residency for native-first v6."""

from __future__ import annotations

import time

from .runtime_handoff import StageReleaseResult, release_stage_patcher
from .runtime_trace import emit
from .runtime_v6 import GIB, hardware_policy

_INSTALLED = False


def install_conditioning_residency_policy() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from . import conditioning_cache

    def release_video_vae(bundle, label: str):
        patcher = getattr(getattr(bundle, "video_vae", None), "patcher", None)
        policy = hardware_policy()
        loaded = 0
        try:
            value = getattr(patcher, "loaded_size", 0)
            loaded = max(0, int(value() if callable(value) else value))
        except (TypeError, ValueError, RuntimeError):
            pass

        if policy.keep_all_hot:
            emit(
                "v6.conditioning.vae.keep",
                memory=True,
                stage=label,
                policy=policy.label,
                loaded_gib=loaded / GIB,
            )
            return StageReleaseResult(
                label,
                "kept-hot-high-vram",
                loaded_before=loaded,
                loaded_after=loaded,
                detail=f"policy={policy.label}",
            )

        started = time.perf_counter()
        result = release_stage_patcher(patcher, label=label)
        emit(
            "v6.conditioning.vae.release",
            memory=True,
            stage=label,
            policy=policy.label,
            mode=result.mode,
            elapsed_s=time.perf_counter() - started,
            loaded_before_gib=result.loaded_before / GIB,
            loaded_after_gib=result.loaded_after / GIB,
        )
        return result

    conditioning_cache._release_video_vae = release_video_vae
    _INSTALLED = True
    emit("v6.conditioning.vae_policy.install", result="installed", policy=hardware_policy().label)


__all__ = ["install_conditioning_residency_policy"]
