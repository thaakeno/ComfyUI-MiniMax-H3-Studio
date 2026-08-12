"""Runtime residency helpers for large H3 stages.

The H3 text encoder, transformer and VAEs are all individually small enough to
fit on common 20+ GiB GPUs when used one stage at a time, but ComfyUI's dynamic
VRAM path may intentionally keep only part of a model resident. That is a good
general default; for H3 it can become much slower than an explicit stage handoff
because the same large quantized weights are streamed repeatedly.

These helpers never take permanent ownership of ComfyUI's model manager. They
ask the manager for a full stage residency only when the *real* stage memory
budget says it is safe, fall back without breaking generation when it is not,
and keep the normal manager as the source of truth for eviction/offload.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterable
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
GIB = 1024**3
SAMPLING_RESIDENCY_WRAPPER_KEY = "h3studio_sampling_residency"


def _model_size(patcher: Any) -> int:
    for name in ("model_size", "model_size_bytes"):
        value = getattr(patcher, name, None)
        try:
            size = int(value() if callable(value) else value)
        except (TypeError, ValueError):
            continue
        if size > 0:
            return size
    model = getattr(patcher, "model", None)
    if model is None:
        return 0
    total = 0
    try:
        for parameter in model.parameters():
            total += parameter.numel() * parameter.element_size()
        for buffer in model.buffers():
            total += buffer.numel() * buffer.element_size()
    except Exception:
        return 0
    return int(total)


def _loaded_size(patcher: Any) -> int:
    value = getattr(patcher, "loaded_size", None)
    try:
        loaded = int(value() if callable(value) else value)
    except (TypeError, ValueError):
        return 0
    return max(0, loaded)


def _sync(device: Any) -> None:
    try:
        import torch

        if getattr(device, "type", "") == "cuda" and torch.cuda.is_available():
            torch.cuda.synchronize(device)
    except Exception:
        pass


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class ResidencyResult:
    label: str
    mode: str
    load_seconds: float = 0.0
    release_seconds: float = 0.0
    model_bytes: int = 0
    loaded_bytes: int = 0
    free_before: int = 0
    free_after: int = 0
    detail: str = ""

    @property
    def full(self) -> bool:
        return self.mode in {"full", "native-full"}

    def summary(self) -> str:
        size = f"{self.model_bytes / GIB:.2f}GiB" if self.model_bytes else "unknown"
        bits = [f"{self.label}_residency={self.mode}", f"size={size}", f"load={self.load_seconds:.3f}s"]
        if self.release_seconds:
            bits.append(f"release={self.release_seconds:.3f}s")
        if self.detail:
            bits.append(self.detail)
        return "; ".join(bits)


@dataclass(slots=True)
class SamplingResidencyPlan:
    mode: str
    model_bytes: int
    adapter_bytes: int
    inference_bytes: int
    projected_bytes: int
    total_vram_bytes: int
    loaded_bytes: int = 0
    prepare_seconds: float = 0.0

    def summary(self) -> str:
        return (
            f"sampling_residency={self.mode}; model={self.model_bytes / GIB:.2f}GiB; "
            f"adapters={self.adapter_bytes / GIB:.2f}GiB; inference={self.inference_bytes / GIB:.2f}GiB; "
            f"projected={self.projected_bytes / GIB:.2f}GiB/{self.total_vram_bytes / GIB:.2f}GiB; "
            f"loaded={self.loaded_bytes / GIB:.2f}GiB; prepare={self.prepare_seconds:.3f}s"
        )


def force_full_residency(patcher: Any, *, label: str, nonfatal: bool = True) -> ResidencyResult:
    """Ask ComfyUI to materialize one patcher completely on its load device."""

    if patcher is None:
        return ResidencyResult(label, "unavailable", detail="no_patcher")

    try:
        import comfy.model_management as mm
    except Exception as exc:
        return ResidencyResult(label, "unavailable", detail=f"manager={type(exc).__name__}")

    device = getattr(patcher, "load_device", None) or mm.get_torch_device()
    model_bytes = _model_size(patcher)
    loaded_before = _loaded_size(patcher)
    try:
        free_before = int(mm.get_free_memory(device))
    except Exception:
        free_before = 0

    started = time.perf_counter()
    try:
        mm.load_models_gpu([patcher], force_full_load=True)
        _sync(device)
    except Exception as exc:
        elapsed = time.perf_counter() - started
        is_oom = False
        with suppress(Exception):
            is_oom = bool(mm.is_oom(exc))
        if not nonfatal and not is_oom:
            raise
        LOGGER.warning(
            "[H3 Studio] %s full residency unavailable after %.2fs (%s); continuing with ComfyUI DynamicVRAM.",
            label,
            elapsed,
            exc,
        )
        with suppress(Exception):
            mm.soft_empty_cache()
        return ResidencyResult(
            label,
            "dynamic-fallback",
            load_seconds=elapsed,
            model_bytes=model_bytes,
            loaded_bytes=loaded_before,
            free_before=free_before,
            detail=f"fallback={type(exc).__name__}",
        )

    elapsed = time.perf_counter() - started
    loaded_after = _loaded_size(patcher)
    try:
        free_after = int(mm.get_free_memory(device))
    except Exception:
        free_after = 0
    result = ResidencyResult(
        label,
        "full",
        load_seconds=elapsed,
        model_bytes=model_bytes,
        loaded_bytes=loaded_after,
        free_before=free_before,
        free_after=free_after,
    )
    LOGGER.info("[H3 Studio] %s", result.summary())
    return result


def release_patcher(patcher: Any, result: ResidencyResult | None = None) -> float:
    """Release only one stage patcher so the next large H3 stage gets the VRAM."""

    if patcher is None:
        return 0.0
    try:
        import comfy.model_management as mm
    except Exception:
        return 0.0
    started = time.perf_counter()
    try:
        unload = getattr(mm, "unload_model_and_clones", None)
        if callable(unload):
            unload(patcher, unload_additional_models=False)
        else:
            return 0.0
        mm.soft_empty_cache()
        device = getattr(patcher, "load_device", None) or mm.get_torch_device()
        _sync(device)
    except Exception as exc:
        LOGGER.debug("[H3 Studio] targeted %s release skipped: %s", getattr(result, "label", "model"), exc)
        return 0.0
    elapsed = time.perf_counter() - started
    if result is not None:
        result.release_seconds = elapsed
    return elapsed


@contextmanager
def text_encoder_residency(clip: Any):
    """Make the CLIP encoder's *native* load full-resident exactly once.

    ComfyUI's ``CLIP.encode_from_tokens`` always calls ``CLIP.load_model``.
    Pre-loading the patcher here and then calling encode caused a second model
    manager pass on H3's dynamic 32B encoder. Instead temporarily replace only
    this CLIP instance's ``load_model`` with the same native implementation plus
    ``force_full_load=True``. The encode itself therefore owns the one and only
    GPU materialization at the correct memory-estimation boundary.
    """

    patcher = getattr(clip, "patcher", None)
    original_load = getattr(clip, "load_model", None)
    if patcher is None or not callable(original_load):
        yield ResidencyResult("text_encoder", "native-dynamic", detail="no_load_hook")
        return

    try:
        import comfy.model_management as mm
    except Exception as exc:
        yield ResidencyResult("text_encoder", "native-dynamic", detail=f"manager={type(exc).__name__}")
        return

    result = ResidencyResult("text_encoder", "native-full-pending", model_bytes=_model_size(patcher))
    had_instance_override = "load_model" in getattr(clip, "__dict__", {})
    previous_override = getattr(clip, "__dict__", {}).get("load_model") if had_instance_override else None

    def native_full_load(tokens=None):
        tokens = {} if tokens is None else tokens
        memory_used = 0
        cond_stage = getattr(clip, "cond_stage_model", None)
        estimator = getattr(cond_stage, "memory_estimation_function", None)
        if callable(estimator):
            with suppress(Exception):
                memory_used = int(estimator(tokens, device=patcher.load_device))

        started = time.perf_counter()
        try:
            mm.load_models_gpu([patcher], memory_required=memory_used, force_full_load=True)
            _sync(getattr(patcher, "load_device", None))
            result.mode = "native-full"
            result.loaded_bytes = _loaded_size(patcher)
            result.detail = f"estimated_activation={memory_used / GIB:.2f}GiB"
            return patcher
        except Exception as exc:
            result.mode = "native-dynamic-fallback"
            result.detail = f"fallback={type(exc).__name__}"
            LOGGER.warning(
                "[H3 Studio] Native full text-encoder load failed (%s); retrying once with ComfyUI's normal dynamic policy.",
                exc,
            )
            return original_load(tokens)
        finally:
            result.load_seconds += time.perf_counter() - started

    try:
        clip.load_model = native_full_load
        yield result
    finally:
        if had_instance_override:
            clip.load_model = previous_override
        else:
            with suppress(AttributeError):
                delattr(clip, "load_model")
        keep = _env_flag("H3STUDIO_KEEP_TEXT_ENCODER")
        if result.mode == "native-full" and not keep:
            release_patcher(patcher, result)
        LOGGER.info("[H3 Studio] %s", result.summary())


def _sampling_plan(model: Any, noise_shape: Any, conds: Any, adapter_bytes: int) -> SamplingResidencyPlan:
    import comfy.model_management as mm
    import comfy.sampler_helpers as sampler_helpers

    device = getattr(model, "load_device", None) or mm.get_torch_device()
    model_bytes = _model_size(model)
    loaded_bytes = _loaded_size(model)
    try:
        total_vram = int(mm.get_total_memory(device))
    except Exception:
        total_vram = 0
    try:
        memory_required, _minimum = sampler_helpers.estimate_memory(model, noise_shape, conds)
        inference_bytes = int(memory_required)
    except Exception as exc:
        LOGGER.debug("[H3 Studio] sampling memory estimate unavailable: %s", exc)
        inference_bytes = 0

    reserve = 0
    with suppress(Exception):
        reserve = int(mm.extra_reserved_memory())
    floor = 0
    with suppress(Exception):
        floor = int(mm.minimum_inference_memory())
    inference_budget = max(floor, inference_bytes + reserve)

    projected = int(model_bytes * 1.10) + int(adapter_bytes) + inference_budget
    safety = float(os.environ.get("H3STUDIO_FULL_DIFFUSION_VRAM_FRACTION", "0.94"))
    safety = min(0.98, max(0.70, safety))
    fits = bool(total_vram and projected <= int(total_vram * safety))
    if _env_flag("H3STUDIO_FORCE_FULL_DIFFUSION"):
        fits = True
    if _env_flag("H3STUDIO_DISABLE_FULL_DIFFUSION"):
        fits = False
    mode = "full-at-sampler" if fits else "dynamic-at-sampler"
    return SamplingResidencyPlan(
        mode=mode,
        model_bytes=model_bytes,
        adapter_bytes=int(adapter_bytes),
        inference_bytes=inference_budget,
        projected_bytes=projected,
        total_vram_bytes=total_vram,
        loaded_bytes=loaded_bytes,
    )


@dataclass(slots=True)
class _SamplingResidencyWrapper:
    adapter_bytes: int = 0
    profile: str = ""

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
        plan = _sampling_plan(model, noise_shape, conds, self.adapter_bytes)
        request_full = bool(force_full_load or (plan.mode == "full-at-sampler" and not force_offload))
        LOGGER.info(
            "[H3 Studio] Sampling memory plan | profile=%s | %s",
            self.profile or "unknown",
            plan.summary(),
        )
        started = time.perf_counter()
        result = executor(
            model,
            noise_shape,
            conds,
            model_options=model_options,
            force_full_load=request_full,
            force_offload=force_offload,
        )
        device = getattr(model, "load_device", None)
        _sync(device)
        plan.prepare_seconds = time.perf_counter() - started
        plan.loaded_bytes = _loaded_size(model)
        LOGGER.info("[H3 Studio] Sampling model prepared | %s", plan.summary())
        return result


def attach_sampling_residency_policy(model: Any, *, adapter_bytes: int = 0, profile: str = "") -> SamplingResidencyPlan:
    """Attach one idempotent PREPARE_SAMPLING policy to a stable model patcher."""

    try:
        import comfy.model_management as mm
        import comfy.patcher_extension

        model.remove_wrappers_with_key(
            comfy.patcher_extension.WrappersMP.PREPARE_SAMPLING,
            SAMPLING_RESIDENCY_WRAPPER_KEY,
        )
        model.add_wrapper_with_key(
            comfy.patcher_extension.WrappersMP.PREPARE_SAMPLING,
            SAMPLING_RESIDENCY_WRAPPER_KEY,
            _SamplingResidencyWrapper(max(0, int(adapter_bytes)), str(profile or "")),
        )
        total = int(mm.get_total_memory(getattr(model, "load_device", None) or mm.get_torch_device()))
    except Exception as exc:
        LOGGER.warning("[H3 Studio] Could not attach sampler residency policy: %s", exc)
        return SamplingResidencyPlan("unavailable", _model_size(model), int(adapter_bytes), 0, 0, 0, _loaded_size(model))
    return SamplingResidencyPlan(
        "deferred-to-sampler",
        _model_size(model),
        int(adapter_bytes),
        0,
        0,
        total,
        _loaded_size(model),
    )


@contextmanager
def vae_full_stage(vae: Any, *, label: str = "vae"):
    """Let ComfyUI force-load the VAE at the exact encode/decode call boundary."""

    if vae is None:
        yield ResidencyResult(label, "unavailable", detail="no_vae")
        return
    old = bool(getattr(vae, "disable_offload", False))
    vae.disable_offload = True
    result = ResidencyResult(label, "native-full-stage", model_bytes=_model_size(getattr(vae, "patcher", None)))
    started = time.perf_counter()
    try:
        yield result
    finally:
        result.load_seconds = time.perf_counter() - started
        vae.disable_offload = old


def prewarm_diffusion_model(model: Any) -> ResidencyResult:
    """Deprecated compatibility helper; use sampler-time residency instead."""

    LOGGER.warning(
        "[H3 Studio] eager diffusion prewarm requested; sampler-time residency is preferred to avoid duplicate loads"
    )
    return force_full_residency(model, label="diffusion")


def prewarm_vae(vae: Any) -> ResidencyResult:
    """Compatibility helper for callers not yet migrated to :func:`vae_full_stage`."""

    return force_full_residency(getattr(vae, "patcher", None), label="vae")


def _host_total_bytes() -> int:
    try:
        pages = int(os.sysconf("SC_PHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        return pages * page_size
    except Exception:
        return 0


def tmpfs_pressure_note(paths: Iterable[str | os.PathLike[str]]) -> str:
    """Return an actionable warning when huge model files consume /dev/shm RAM."""

    total = _host_total_bytes()
    if total <= 0:
        return ""
    tmpfs_bytes = 0
    tmpfs_files = 0
    for value in paths:
        if not value:
            continue
        try:
            path = Path(value).resolve()
            if path == Path("/dev/shm") or Path("/dev/shm") in path.parents:
                tmpfs_bytes += path.stat().st_size
                tmpfs_files += 1
        except OSError:
            continue
    if not tmpfs_files:
        return ""
    ratio = tmpfs_bytes / total
    if ratio < 0.20 and total >= 48 * GIB:
        return ""
    return (
        f"{tmpfs_files} selected model file(s) occupy {tmpfs_bytes / GIB:.1f} GiB of /dev/shm on a "
        f"{total / GIB:.1f} GiB host. tmpfs competes with ComfyUI's staged CPU weights and can turn H3 loads into "
        "multi-minute memory thrashing. Prefer persistent /teamspace or disk-backed model paths on low-RAM instances."
    )
