"""Manager-owned handoffs between MiniMax H3's giant sequential stages.

H3 naturally runs text encoder -> diffusion transformer -> video VAE. On
memory-constrained GPUs those stages should not compete for residency. Current
ComfyUI intentionally keeps dynamic models around for other dynamic models, so
Studio explicitly asks the *public Comfy manager* to release a completed stage.

This module never performs direct partial patcher unloads, never preloads the
next stage, and never changes quantization or model math. The next stage is still
loaded normally by ComfyUI at the point where it is actually used.
"""

from __future__ import annotations

import inspect
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)
GIB = 1024**3
POST_SAMPLE_RELEASE_KEY = "h3studio_release_diffusion_after_sampling"


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def stage_handoffs_enabled() -> bool:
    """Allow a clean A/B without reverting the manager-safe production path."""

    return not _env_flag("H3STUDIO_DISABLE_STAGE_HANDOFFS")


def _loaded_size(patcher: Any) -> int:
    if patcher is None:
        return 0
    value = getattr(patcher, "loaded_size", 0)
    try:
        return max(0, int(value() if callable(value) else value))
    except (TypeError, ValueError, RuntimeError):
        return 0


@dataclass(frozen=True, slots=True)
class StageReleaseResult:
    label: str
    mode: str
    elapsed_seconds: float = 0.0
    loaded_before: int = 0
    loaded_after: int = 0
    detail: str = ""

    def summary(self) -> str:
        bits = [
            f"{self.label}_handoff={self.mode}",
            f"loaded={self.loaded_before / GIB:.2f}->{self.loaded_after / GIB:.2f}GiB",
            f"release={self.elapsed_seconds:.3f}s",
        ]
        if self.detail:
            bits.append(self.detail)
        return "; ".join(bits)


def release_stage_patcher(patcher: Any, *, label: str) -> StageReleaseResult:
    """Ask ComfyUI to unload exactly one completed patcher and its clones.

    ``unload_model_and_clones`` is the current manager-level targeted unload API.
    Using it *after* a stage avoids the old H3 regression where Studio preloaded
    a model and the native encode/sampler immediately performed a second manager
    pass. We deliberately do not call ``soft_empty_cache`` ourselves: ComfyUI's
    unload path owns cache cleanup when an actual unload occurs.
    """

    if patcher is None:
        return StageReleaseResult(label, "unavailable", detail="no_patcher")
    if not stage_handoffs_enabled():
        return StageReleaseResult(label, "disabled-by-env", loaded_before=_loaded_size(patcher))

    before = _loaded_size(patcher)
    try:
        import comfy.model_management as mm
    except Exception as exc:
        return StageReleaseResult(label, "unavailable", loaded_before=before, detail=f"manager={type(exc).__name__}")

    unload = getattr(mm, "unload_model_and_clones", None)
    if not callable(unload):
        return StageReleaseResult(label, "unavailable", loaded_before=before, detail="manager_api=missing")

    started = time.perf_counter()
    try:
        try:
            parameters = inspect.signature(unload).parameters
        except (TypeError, ValueError):
            parameters = {}
        if "unload_additional_models" in parameters:
            unload(patcher, unload_additional_models=False)
        else:
            unload(patcher)
    except Exception as exc:
        elapsed = time.perf_counter() - started
        result = StageReleaseResult(
            label,
            "failed-nonfatal",
            elapsed_seconds=elapsed,
            loaded_before=before,
            loaded_after=_loaded_size(patcher),
            detail=f"error={type(exc).__name__}",
        )
        LOGGER.warning("[H3 Studio] Manager stage release failed nonfatally | %s", result.summary())
        return result

    elapsed = time.perf_counter() - started
    after = _loaded_size(patcher)
    if before <= 0:
        mode = "already-offloaded"
    elif after <= 0:
        mode = "released"
    elif after < before:
        mode = "partially-released-by-manager"
    else:
        mode = "manager-requested"
    result = StageReleaseResult(label, mode, elapsed, before, after)
    LOGGER.info("[H3 Studio] Stage handoff | %s", result.summary())
    return result


@dataclass(slots=True)
class _ReleaseAfterSampling:
    patcher: Any

    def __call__(
        self,
        executor,
        noise,
        latent_image,
        sampler,
        sigmas,
        denoise_mask,
        callback,
        disable_pbar,
        seed,
        latent_shapes,
    ):
        try:
            return executor(
                noise,
                latent_image,
                sampler,
                sigmas,
                denoise_mask,
                callback,
                disable_pbar,
                seed,
                latent_shapes=latent_shapes,
            )
        finally:
            release_stage_patcher(self.patcher, label="diffusion")


def attach_sampling_stage_release(model: Any) -> str:
    """Release the transformer after denoising, before graph execution reaches VAE decode."""

    if not stage_handoffs_enabled():
        return "disabled-by-env"
    try:
        import comfy.patcher_extension

        wrapper_type = comfy.patcher_extension.WrappersMP.OUTER_SAMPLE
        model.remove_wrappers_with_key(wrapper_type, POST_SAMPLE_RELEASE_KEY)
        model.add_wrapper_with_key(wrapper_type, POST_SAMPLE_RELEASE_KEY, _ReleaseAfterSampling(model))
        return "manager-targeted"
    except Exception as exc:
        LOGGER.debug("[H3 Studio] Could not attach post-sampling stage release: %s", exc)
        return "unavailable"
