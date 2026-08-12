"""Structured tracing around H3 bundle route changes without changing behavior."""

from __future__ import annotations

import time

from .nodes.loader import H3StudioBundle
from .runtime_trace import emit

_INSTALLED = False
_ORIGINAL_MODEL_FOR = H3StudioBundle.model_for
_ORIGINAL_RELEASE_MODEL = H3StudioBundle.release_model


def install_bundle_route_trace() -> None:
    global _INSTALLED
    if _INSTALLED:
        emit("bundle.route_trace.install", result="already-installed")
        return

    def release_model(self):
        previous_name = str(getattr(self, "_model_name", "") or "")
        previous_kind = str(getattr(self, "_model_kind", "") or "")
        previous_model = getattr(self, "_model", None)
        started = time.perf_counter()
        emit(
            "transformer.release.begin",
            memory=True,
            models=True,
            route=previous_kind or "none",
            name=previous_name or "none",
            patcher_id=id(previous_model) if previous_model is not None else 0,
        )
        result = _ORIGINAL_RELEASE_MODEL(self)
        emit(
            "transformer.release.end",
            memory=True,
            models=True,
            elapsed_s=time.perf_counter() - started,
            route=previous_kind or "none",
            name=previous_name or "none",
            patcher_id=id(previous_model) if previous_model is not None else 0,
        )
        return result

    def model_for(self, kind: str):
        requested_kind = "ref2va" if kind == "ref2va" else "fl2va"
        requested_name = self.selected_name(requested_kind)
        current = getattr(self, "_model", None)
        current_name = str(getattr(self, "_model_name", "") or "")
        if current is not None and current_name == requested_name:
            emit(
                "transformer.route.hit",
                memory=True,
                models=True,
                route=requested_kind,
                name=requested_name,
                patcher_id=id(current),
                model_id=id(getattr(current, "model", current)),
            )
        else:
            emit(
                "transformer.route.miss",
                memory=True,
                models=True,
                route=requested_kind,
                name=requested_name,
                previous_name=current_name or "none",
                previous_patcher_id=id(current) if current is not None else 0,
            )

        started = time.perf_counter()
        try:
            result = _ORIGINAL_MODEL_FOR(self, kind)
        except Exception as exc:
            emit(
                "transformer.route.error",
                memory=True,
                models=True,
                elapsed_s=time.perf_counter() - started,
                route=requested_kind,
                name=requested_name,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise
        emit(
            "transformer.route.ready",
            memory=True,
            models=True,
            elapsed_s=time.perf_counter() - started,
            route=requested_kind,
            name=requested_name,
            patcher_id=id(result),
            model_id=id(getattr(result, "model", result)),
        )
        return result

    H3StudioBundle.release_model = release_model
    H3StudioBundle.model_for = model_for
    _INSTALLED = True
    emit("bundle.route_trace.install", result="installed")


__all__ = ["install_bundle_route_trace"]
