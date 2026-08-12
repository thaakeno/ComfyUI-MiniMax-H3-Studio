"""Low-overhead structured runtime tracing for H3 Studio.

The trace is intentionally stage-boundary only. It never synchronizes CUDA,
loads or unloads models, clears caches, or walks tensors. This makes it useful
for diagnosing slow model-manager transitions without becoming part of the hot
sampling path itself.
"""

from __future__ import annotations

import itertools
import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

LOGGER = logging.getLogger(__name__)
PREFIX = "[H3 Studio Trace]"
GIB = 1024**3
_SEQ = itertools.count(1)
_PROCESS_STARTED = time.perf_counter()


def _flag(name: str, default: bool = True) -> bool:
    value = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def enabled() -> bool:
    return _flag("H3STUDIO_STRUCTURED_TRACE", True)


def memory_enabled() -> bool:
    return _flag("H3STUDIO_TRACE_MEMORY", True)


def models_enabled() -> bool:
    # Expanded model lists make each console line much larger and add no value
    # for normal runs. They remain available for one-off deep diagnostics.
    return _flag("H3STUDIO_TRACE_MODELS", False)


def _clean(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4f}"
    text = str(value).replace("\n", "\\n").replace("\r", "\\r")
    return text.replace(" | ", "/")


def _process_io_fields() -> dict[str, Any]:
    try:
        with open("/proc/self/io", encoding="utf-8") as handle:
            values = {}
            for line in handle:
                key, _, value = line.partition(":")
                if key in {"read_bytes", "write_bytes"}:
                    values[key] = int(value.strip())
        return {
            "io_read_gib": round(values.get("read_bytes", 0) / GIB, 3),
            "io_write_gib": round(values.get("write_bytes", 0) / GIB, 3),
        }
    except Exception:
        return {}


def _memory_fields() -> dict[str, Any]:
    if not memory_enabled():
        return {}

    fields: dict[str, Any] = {}
    try:
        import psutil

        vm = psutil.virtual_memory()
        process = psutil.Process()
        fields["ram_free_gib"] = round(int(vm.available) / GIB, 3)
        fields["rss_gib"] = round(int(process.memory_info().rss) / GIB, 3)
    except Exception:
        pass

    try:
        import comfy.model_management as mm

        fields["pinned_gib"] = round(int(getattr(mm, "TOTAL_PINNED_MEMORY", 0)) / GIB, 3)
        fields["pin_budget_gib"] = round(max(0, int(getattr(mm, "MAX_PINNED_MEMORY", 0))) / GIB, 3)
        args = getattr(mm, "args", None)
        if args is not None:
            fields["fast_disk"] = bool(getattr(args, "fast_disk", False))
    except Exception:
        pass

    fields.update(_process_io_fields())

    try:
        import torch

        if torch.cuda.is_available():
            device = torch.cuda.current_device()
            free, total = torch.cuda.mem_get_info(device)
            fields["vram_free_gib"] = round(int(free) / GIB, 3)
            fields["vram_total_gib"] = round(int(total) / GIB, 3)
            fields["cuda_alloc_gib"] = round(int(torch.cuda.memory_allocated(device)) / GIB, 3)
            fields["cuda_reserved_gib"] = round(int(torch.cuda.memory_reserved(device)) / GIB, 3)
    except Exception:
        pass
    return fields


def _model_fields() -> dict[str, Any]:
    if not models_enabled():
        return {}
    try:
        import comfy.model_management as mm

        getter = getattr(mm, "loaded_models", None)
        if not callable(getter):
            return {}
        models = tuple(getter())
        entries: list[str] = []
        for patcher in models:
            model = getattr(patcher, "model", None)
            name = type(model).__name__ if model is not None else type(patcher).__name__
            try:
                loaded = int(patcher.loaded_size()) / GIB
            except Exception:
                loaded = 0.0
            try:
                size = int(patcher.model_size()) / GIB
            except Exception:
                size = 0.0
            entries.append(f"{name}:{loaded:.2f}/{size:.2f}GiB")
        return {
            "loaded_model_count": len(models),
            "loaded_models": ",".join(entries) if entries else "none",
        }
    except Exception:
        return {}


def emit(event: str, *, memory: bool = False, models: bool = False, **fields: Any) -> None:
    """Emit one stable key=value line suitable for grep/diffing between runs."""

    if not enabled():
        return
    payload: dict[str, Any] = {
        "seq": next(_SEQ),
        "uptime_s": time.perf_counter() - _PROCESS_STARTED,
        "event": event,
        **fields,
    }
    if memory:
        payload.update(_memory_fields())
    if models:
        payload.update(_model_fields())
    LOGGER.info("%s %s", PREFIX, " | ".join(f"{key}={_clean(value)}" for key, value in payload.items()))


@contextmanager
def span(event: str, *, memory: bool = False, models: bool = False, **fields: Any) -> Iterator[dict[str, Any]]:
    """Emit begin/end/error events around a non-hot-path stage."""

    started = time.perf_counter()
    state: dict[str, Any] = {}
    emit(f"{event}.begin", memory=memory, models=models, **fields)
    try:
        yield state
    except Exception as exc:
        emit(
            f"{event}.error",
            memory=True,
            models=True,
            elapsed_s=time.perf_counter() - started,
            error_type=type(exc).__name__,
            error=str(exc),
            **fields,
        )
        raise
    else:
        emit(
            f"{event}.end",
            memory=memory,
            models=models,
            elapsed_s=time.perf_counter() - started,
            **fields,
            **state,
        )


__all__ = ["emit", "enabled", "memory_enabled", "models_enabled", "span"]
