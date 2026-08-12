"""Runtime stability policy for memory-constrained MiniMax H3 sessions.

This module intentionally prefers proven native ComfyUI model-manager behavior
for the expensive H3 text/diffusion stages. It also prevents the optional TAEH3
preview worker from competing with DynamicVRAM/async-offload on low-RAM hosts.
"""

from __future__ import annotations

import logging
import os
from contextlib import suppress
from typing import Any

LOGGER = logging.getLogger(__name__)
GIB = 1024**3
LOW_RAM_THRESHOLD = 48 * GIB
FAST_PREVIEW_MAX_RESOLUTION = 320
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
            "This reduces duplicate host-weight buffering; real model files in /dev/shm should still be moved to persistent storage.",
            total_ram / GIB,
        )
        return "enabled"
    except Exception as exc:
        LOGGER.debug("[H3 Studio] Automatic fast-disk setup skipped: %s", exc)
        return "unavailable"


def accelerated_preview_steps(total_steps: int) -> frozenset[int]:
    """Return sampler indices allowed to create a tiny preview on short runs."""

    total_steps = max(0, int(total_steps))
    if total_steps <= 0:
        return frozenset()
    if total_steps <= 8:
        # One early frame is enough to prove that an accelerated run is alive.
        # Extra CPU TAEH3 decodes can steal the exact host bandwidth that
        # DynamicVRAM needs for diffusion-weight streaming.
        return frozenset({0})
    return frozenset(range(total_steps))


def _drain_pending_preview_jobs(wrapper: Any) -> None:
    jobs = getattr(wrapper, "_jobs", None)
    if jobs is None:
        return
    while True:
        try:
            jobs.get_nowait()
        except Exception:
            break
        else:
            with suppress(Exception):
                jobs.task_done()


def _install_preview_stability_guard() -> bool:
    """Make TAEH3 opportunistic rather than a competing inference workload."""

    try:
        from .nodes import preview as preview_module

        wrapper_cls = preview_module._PreviewWrapper
    except Exception as exc:
        LOGGER.debug("[H3 Studio] Preview stability guard unavailable: %s", exc)
        return False

    if bool(getattr(wrapper_cls, "__h3studio_stability_guard__", False)):
        return True

    original_enqueue = wrapper_cls._enqueue
    original_send = wrapper_cls._send_decoded
    original_call = wrapper_cls.__call__

    def stable_enqueue(
        self,
        torch,
        step,
        x0,
        total_steps,
        latent_shapes,
        run_id,
        elapsed_seconds,
        average_step_seconds,
    ):
        total_steps_i = int(total_steps)
        if total_steps_i <= 8 and int(step) not in accelerated_preview_steps(total_steps_i):
            return
        if float(getattr(self, "_h3studio_last_preview_seconds", 0.0)) > 1.25 and int(step) > 0:
            return
        old_max = int(getattr(self, "max_resolution", FAST_PREVIEW_MAX_RESOLUTION))
        if total_steps_i <= 8:
            self.max_resolution = min(old_max, FAST_PREVIEW_MAX_RESOLUTION)
        try:
            return original_enqueue(
                self,
                torch,
                step,
                x0,
                total_steps,
                latent_shapes,
                run_id,
                elapsed_seconds,
                average_step_seconds,
            )
        finally:
            self.max_resolution = old_max

    def stable_send(self, torch, job):
        import time

        started = time.perf_counter()
        try:
            return original_send(self, torch, job)
        finally:
            elapsed = time.perf_counter() - started
            self._h3studio_last_preview_seconds = elapsed
            if elapsed > 1.25:
                LOGGER.warning(
                    "[H3 Studio] TAEH3 preview took %.2fs on the CPU; suppressing further accelerated-run previews so inference keeps priority.",
                    elapsed,
                )

    def stable_call(self, *args, **kwargs):
        self._h3studio_last_preview_seconds = 0.0
        try:
            return original_call(self, *args, **kwargs)
        finally:
            # No preview is useful after sampling. Invalidate and drain queued
            # jobs so CPU preview work cannot overlap exact H3 VAE decode.
            self.active_run_id = ""
            _drain_pending_preview_jobs(self)

    wrapper_cls._enqueue = stable_enqueue
    wrapper_cls._send_decoded = stable_send
    wrapper_cls.__call__ = stable_call
    wrapper_cls.__h3studio_stability_guard__ = True
    return True


def _remove_experimental_sampling_residency(model: Any) -> bool:
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

    from .nodes.performance import H3StudioFastDecode, H3StudioOptimizedContextSamplingPreset

    class H3StudioStableContextSamplingPreset(H3StudioOptimizedContextSamplingPreset):
        """Keep acceleration/LoRA caching but leave diffusion residency to ComfyUI."""

        def build(self, model, studio_context):
            built_model, sampler, sigmas, info = super().build(model, studio_context)
            if not _env_flag("H3STUDIO_EXPERIMENTAL_FULL_DIFFUSION"):
                _remove_experimental_sampling_residency(built_model)
                info = f"{info} | sampling_residency=native-comfy-manager"
                LOGGER.info("[H3 Studio] Sampling residency restored to native ComfyUI manager")
            return built_model, sampler, sigmas, info

    class H3StudioStableDecode(H3StudioFastDecode):
        """Exact H3 decode with an explicit old-core diagnostic."""

        def decode(self, samples, vae):
            first_stage = getattr(vae, "first_stage_model", None)
            if not bool(getattr(first_stage, "comfy_has_chunked_io", False)):
                LOGGER.warning(
                    "[H3 Studio] This ComfyUI core lacks MiniMax H3 chunked VAE I/O. Exact decode can become extremely slow or memory-heavy. "
                    "Update ComfyUI to a build containing the H3 chunked-I/O changes before judging decode performance."
                )
            return super().decode(samples, vae)

    _RUNTIME_NODE_CLASSES = H3StudioStableContextSamplingPreset, H3StudioStableDecode
    return _RUNTIME_NODE_CLASSES


def install_runtime_stability() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    configure_low_ram_fast_disk()
    _install_preview_stability_guard()
