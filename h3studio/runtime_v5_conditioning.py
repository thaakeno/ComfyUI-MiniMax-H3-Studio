"""High-VRAM conditioning residency override for max-speed v5."""

from __future__ import annotations

from .runtime_handoff import StageReleaseResult, release_stage_patcher
from .runtime_v5 import hardware_policy

_INSTALLED = False


def install_conditioning_residency_policy() -> None:
    """Keep the H3 VAE resident only when the hardware can hold all major stages."""

    global _INSTALLED
    if _INSTALLED:
        return

    from . import conditioning_cache

    def release_video_vae(bundle, label: str):
        patcher = getattr(getattr(bundle, "video_vae", None), "patcher", None)
        policy = hardware_policy()
        if policy.keep_all_hot:
            loaded = 0
            try:
                value = getattr(patcher, "loaded_size", 0)
                loaded = max(0, int(value() if callable(value) else value))
            except (TypeError, ValueError, RuntimeError):
                pass
            return StageReleaseResult(
                label,
                "kept-hot-high-vram",
                loaded_before=loaded,
                loaded_after=loaded,
                detail=f"policy={policy.label}",
            )
        return release_stage_patcher(patcher, label=label)

    conditioning_cache._release_video_vae = release_video_vae
    _INSTALLED = True


__all__ = ["install_conditioning_residency_policy"]
