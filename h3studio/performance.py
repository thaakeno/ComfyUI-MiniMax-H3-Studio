"""Small H3 performance helpers that do not take over model residency.

Production text-encoder and diffusion stages are owned by ComfyUI's native
model manager. Sequential stage cleanup lives in :mod:`runtime_handoff` and is
manager-targeted only after a stage has completed. The sole residency override
left here is the legacy-core VAE fallback used when upstream H3 chunked I/O is
not available.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GIB = 1024**3


def _model_size(patcher: Any) -> int:
    if patcher is None:
        return 0
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


@dataclass(slots=True)
class ResidencyResult:
    label: str
    mode: str
    load_seconds: float = 0.0
    model_bytes: int = 0
    detail: str = ""

    def summary(self) -> str:
        size = f"{self.model_bytes / GIB:.2f}GiB" if self.model_bytes else "unknown"
        bits = [f"{self.label}_residency={self.mode}", f"size={size}", f"load={self.load_seconds:.3f}s"]
        if self.detail:
            bits.append(self.detail)
        return "; ".join(bits)


@contextmanager
def vae_full_stage(vae: Any, *, label: str = "vae"):
    """Legacy-core fallback: ask Comfy's VAE wrapper to avoid per-tile offload.

    Current MiniMax H3 cores with ``comfy_has_chunked_io`` bypass this helper
    entirely. It remains only for old cores where the previous tiled path can
    repeatedly stream the same decoder weights.
    """

    if vae is None:
        yield ResidencyResult(label, "unavailable", detail="no_vae")
        return
    old = bool(getattr(vae, "disable_offload", False))
    vae.disable_offload = True
    result = ResidencyResult(
        label,
        "legacy-full-stage",
        model_bytes=_model_size(getattr(vae, "patcher", None)),
    )
    started = time.perf_counter()
    try:
        yield result
    finally:
        result.load_seconds = time.perf_counter() - started
        vae.disable_offload = old


def _host_total_bytes() -> int:
    try:
        pages = int(os.sysconf("SC_PHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        return pages * page_size
    except Exception:
        return 0


def tmpfs_pressure_note(paths: Iterable[str | os.PathLike[str]]) -> str:
    """Return an actionable warning when huge selected model files consume /dev/shm RAM."""

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
