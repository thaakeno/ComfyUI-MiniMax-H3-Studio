"""Runtime residency helpers for large H3 stages.

The H3 text encoder, transformer and VAEs are all individually small enough to
fit on common 20+ GiB GPUs when used one stage at a time, but ComfyUI's dynamic
VRAM path may intentionally keep only part of a model resident. That is a good
general default; for H3 it can become much slower than an explicit stage handoff
because the same large quantized weights are streamed repeatedly.

These helpers never take permanent ownership of ComfyUI's model manager. They
ask the manager for a full stage residency when it is useful, fall back without
breaking generation when that cannot be satisfied, and keep the normal manager
as the source of truth for eviction/offload.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

LOGGER = logging.getLogger(__name__)
GIB = 1024**3


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
        return self.mode == "full"

    def summary(self) -> str:
        size = f"{self.model_bytes / GIB:.2f}GiB" if self.model_bytes else "unknown"
        bits = [f"{self.label}_residency={self.mode}", f"size={size}", f"load={self.load_seconds:.3f}s"]
        if self.release_seconds:
            bits.append(f"release={self.release_seconds:.3f}s")
        if self.detail:
            bits.append(self.detail)
        return "; ".join(bits)


def force_full_residency(patcher: Any, *, label: str, nonfatal: bool = True) -> ResidencyResult:
    """Ask ComfyUI to materialize one patcher completely on its load device.

    On quantized H3 this avoids per-layer DynamicVRAM transfers during the next
    encode/sample/decode stage. The manager is still allowed to evict other
    models to make room. If a full load does not fit, the optimization degrades
    to the normal ComfyUI path instead of making the workflow unusable.
    """

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
        try:
            is_oom = bool(mm.is_oom(exc))
        except Exception:
            pass
        if not nonfatal and not is_oom:
            raise
        LOGGER.warning(
            "[H3 Studio] %s full residency unavailable after %.2fs (%s); continuing with ComfyUI DynamicVRAM.",
            label,
            elapsed,
            exc,
        )
        try:
            mm.soft_empty_cache()
        except Exception:
            pass
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
            # Older managers do not expose targeted unloading. Avoid a global
            # unload unless explicitly requested; normal allocation can evict it.
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
    """Fully stage the H3 32B encoder only for an actual cache-miss encode."""

    patcher = getattr(clip, "patcher", None)
    result = force_full_residency(patcher, label="text_encoder")
    try:
        yield result
    finally:
        keep = str(os.environ.get("H3STUDIO_KEEP_TEXT_ENCODER", "0")).strip().lower() in {"1", "true", "yes", "on"}
        if result.full and not keep:
            release_patcher(patcher, result)


def prewarm_diffusion_model(model: Any) -> ResidencyResult:
    """Materialize the selected H3 transformer before KSampler starts.

    This moves the expensive DynamicVRAM materialization out of KSampler's
    opaque ``Model Initializing`` phase and, when the full model fits, prevents
    repeated layer streaming during each denoise step.
    """

    return force_full_residency(model, label="diffusion")


def prewarm_vae(vae: Any) -> ResidencyResult:
    """Make the final VAE fully resident before its tiled H3 decoder loops."""

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
