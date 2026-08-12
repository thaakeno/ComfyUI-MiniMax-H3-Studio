"""Passive runtime instrumentation for MiniMax H3's large sequential stages.

Diagnostics never request model loads, unloads, CUDA synchronization, or cache
clears. They only observe ComfyUI/PyTorch/psutil state around the native manager
calls so L4 residency variance can be diagnosed without changing the behavior
being measured.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)
GIB = 1024**3
PREPARE_DIAGNOSTICS_KEY = "h3studio_runtime_prepare_diagnostics"
SAMPLE_DIAGNOSTICS_KEY = "h3studio_runtime_sample_diagnostics"


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def diagnostics_enabled() -> bool:
    return _env_flag("H3STUDIO_RUNTIME_DIAGNOSTICS", True)


def _int_value(value: Any) -> int:
    try:
        return int(value() if callable(value) else value)
    except (TypeError, ValueError, RuntimeError):
        return 0


def _patcher_value(patcher: Any, name: str) -> int:
    if patcher is None:
        return 0
    return _int_value(getattr(patcher, name, 0))


def _patcher_name(patcher: Any) -> str:
    model = getattr(patcher, "model", None)
    return type(model).__name__ if model is not None else type(patcher).__name__


def _loaded_model_summary(mm: Any) -> tuple[str, int]:
    getter = getattr(mm, "loaded_models", None)
    if not callable(getter):
        return "unavailable", 0

    entries: list[str] = []
    dynamic_count = 0
    try:
        models = tuple(getter())
    except Exception:
        return "unavailable", 0

    for patcher in models:
        dynamic = False
        checker = getattr(patcher, "is_dynamic", None)
        try:
            dynamic = bool(checker()) if callable(checker) else False
        except Exception:
            dynamic = False
        dynamic_count += int(dynamic)

        size = _patcher_value(patcher, "model_size")
        loaded = _patcher_value(patcher, "loaded_size")
        ram = _patcher_value(patcher, "loaded_ram_size")
        entries.append(
            f"{_patcher_name(patcher)}:"
            f"{loaded / GIB:.2f}/{size / GIB:.2f}GiB-vram:"
            f"{ram / GIB:.2f}GiB-ram:"
            f"{'dyn' if dynamic else 'static'}"
        )
    return ",".join(entries) if entries else "none", dynamic_count


@dataclass(frozen=True, slots=True)
class RuntimeState:
    host_available: int = 0
    process_rss: int = 0
    io_read_bytes: int = 0
    cuda_free: int = 0
    cuda_total: int = 0
    cuda_allocated: int = 0
    cuda_reserved: int = 0
    pinned_memory: int = 0
    patcher_size: int = 0
    patcher_loaded: int = 0
    patcher_ram: int = 0
    dynamic_models: int = 0
    loaded_models: str = "unavailable"


def capture_runtime_state(patcher: Any = None) -> RuntimeState:
    """Capture manager/memory counters without forcing synchronization."""

    host_available = process_rss = io_read_bytes = 0
    cuda_free = cuda_total = cuda_allocated = cuda_reserved = 0
    pinned_memory = 0
    dynamic_models = 0
    loaded_summary = "unavailable"

    try:
        import psutil

        host_available = int(psutil.virtual_memory().available)
        process = psutil.Process()
        process_rss = int(process.memory_info().rss)
        try:
            io_read_bytes = int(process.io_counters().read_bytes)
        except (AttributeError, OSError, PermissionError):
            pass
    except Exception:
        pass

    try:
        import comfy.model_management as mm

        pinned_memory = _int_value(getattr(mm, "TOTAL_PINNED_MEMORY", 0))
        loaded_summary, dynamic_models = _loaded_model_summary(mm)

        try:
            import torch

            device = getattr(patcher, "load_device", None) or mm.get_torch_device()
            if torch.cuda.is_available() and getattr(device, "type", "") == "cuda":
                cuda_free, cuda_total = (int(value) for value in torch.cuda.mem_get_info(device))
                cuda_allocated = int(torch.cuda.memory_allocated(device))
                cuda_reserved = int(torch.cuda.memory_reserved(device))
        except Exception:
            pass
    except Exception:
        pass

    return RuntimeState(
        host_available=host_available,
        process_rss=process_rss,
        io_read_bytes=io_read_bytes,
        cuda_free=cuda_free,
        cuda_total=cuda_total,
        cuda_allocated=cuda_allocated,
        cuda_reserved=cuda_reserved,
        pinned_memory=pinned_memory,
        patcher_size=_patcher_value(patcher, "model_size"),
        patcher_loaded=_patcher_value(patcher, "loaded_size"),
        patcher_ram=_patcher_value(patcher, "loaded_ram_size"),
        dynamic_models=dynamic_models,
        loaded_models=loaded_summary,
    )


def runtime_snapshot(
    stage: str,
    *,
    patcher: Any = None,
    previous: RuntimeState | None = None,
    elapsed: float | None = None,
    detail: str = "",
) -> RuntimeState | None:
    """Log one compact H3 stage snapshot and return it for delta measurements."""

    if not diagnostics_enabled():
        return None

    state = capture_runtime_state(patcher)
    bits = [f"stage={stage}"]
    if elapsed is not None:
        bits.append(f"elapsed={float(elapsed):.3f}s")

    if state.cuda_total:
        bits.extend(
            (
                f"cuda_free={state.cuda_free / GIB:.2f}/{state.cuda_total / GIB:.2f}GiB",
                f"cuda_alloc={state.cuda_allocated / GIB:.2f}GiB",
                f"cuda_reserved={state.cuda_reserved / GIB:.2f}GiB",
            )
        )
    if state.host_available:
        bits.append(f"host_available={state.host_available / GIB:.2f}GiB")
    if state.process_rss:
        bits.append(f"rss={state.process_rss / GIB:.2f}GiB")
    if state.pinned_memory:
        bits.append(f"pinned={state.pinned_memory / GIB:.2f}GiB")

    if patcher is not None:
        bits.extend(
            (
                f"patcher={_patcher_name(patcher)}",
                f"patcher_loaded={state.patcher_loaded / GIB:.2f}/{state.patcher_size / GIB:.2f}GiB",
                f"patcher_ram={state.patcher_ram / GIB:.2f}GiB",
            )
        )

    bits.append(f"dynamic_models={state.dynamic_models}")
    bits.append(f"loaded=[{state.loaded_models}]")

    if previous is not None:
        bits.append(f"io_read_delta={(state.io_read_bytes - previous.io_read_bytes) / GIB:.3f}GiB")
        bits.append(f"rss_delta={(state.process_rss - previous.process_rss) / GIB:+.3f}GiB")
        bits.append(f"host_available_delta={(state.host_available - previous.host_available) / GIB:+.3f}GiB")
        if state.cuda_total and previous.cuda_total:
            bits.append(f"cuda_free_delta={(state.cuda_free - previous.cuda_free) / GIB:+.3f}GiB")
    elif state.io_read_bytes:
        bits.append(f"io_read_total={state.io_read_bytes / GIB:.3f}GiB")

    if detail:
        bits.append(str(detail))

    LOGGER.info("[H3 Studio Runtime] %s", " | ".join(bits))
    return state


@dataclass(slots=True)
class _PrepareSamplingDiagnostics:
    patcher: Any

    def __call__(
        self,
        executor,
        model,
        noise_shape,
        conds,
        model_options=None,
        force_full_load=False,
        force_offload=False,
    ):
        before = runtime_snapshot("sampler_prepare.before", patcher=model)
        started = time.perf_counter()
        result = executor(
            model,
            noise_shape,
            conds,
            model_options=model_options,
            force_full_load=force_full_load,
            force_offload=force_offload,
        )
        runtime_snapshot(
            "sampler_prepare.after",
            patcher=model,
            previous=before,
            elapsed=time.perf_counter() - started,
            detail=f"force_full={bool(force_full_load)} force_offload={bool(force_offload)}",
        )
        return result


@dataclass(slots=True)
class _OuterSampleDiagnostics:
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
        started = time.perf_counter()
        previous_step = started
        run_before = runtime_snapshot("sampling.before", patcher=self.patcher)

        def measured_callback(step, x0, x, total_steps):
            nonlocal previous_step
            now = time.perf_counter()
            step_elapsed = now - previous_step
            previous_step = now
            if _env_flag("H3STUDIO_RUNTIME_STEP_DIAGNOSTICS", True):
                runtime_snapshot(
                    f"sampling.step.{int(step) + 1}/{int(total_steps)}",
                    patcher=self.patcher,
                    elapsed=step_elapsed,
                )
            if callback is not None:
                callback(step, x0, x, total_steps)

        try:
            return executor(
                noise,
                latent_image,
                sampler,
                sigmas,
                denoise_mask,
                measured_callback,
                disable_pbar,
                seed,
                latent_shapes=latent_shapes,
            )
        finally:
            runtime_snapshot(
                "sampling.after",
                patcher=self.patcher,
                previous=run_before,
                elapsed=time.perf_counter() - started,
            )


def attach_sampling_diagnostics(model: Any) -> str:
    """Attach transparent manager/step telemetry without changing load policy."""

    if not diagnostics_enabled():
        return "disabled"

    try:
        import comfy.patcher_extension

        wrappers = comfy.patcher_extension.WrappersMP
        model.remove_wrappers_with_key(wrappers.PREPARE_SAMPLING, PREPARE_DIAGNOSTICS_KEY)
        model.remove_wrappers_with_key(wrappers.OUTER_SAMPLE, SAMPLE_DIAGNOSTICS_KEY)
        model.add_wrapper_with_key(
            wrappers.PREPARE_SAMPLING,
            PREPARE_DIAGNOSTICS_KEY,
            _PrepareSamplingDiagnostics(model),
        )
        model.add_wrapper_with_key(
            wrappers.OUTER_SAMPLE,
            SAMPLE_DIAGNOSTICS_KEY,
            _OuterSampleDiagnostics(model),
        )
        return "passive"
    except Exception as exc:
        LOGGER.debug("[H3 Studio Runtime] Sampling diagnostics unavailable: %s", exc)
        return "unavailable"
