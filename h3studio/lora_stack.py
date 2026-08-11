"""User-selected H3 LoRA stacking with fast quantized-model patching."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from .acceleration import PDDBackendError, _load_model_lora

LOGGER = logging.getLogger(__name__)
MAX_CUSTOM_LORAS = 6
MIN_LORA_STRENGTH = -4.0
MAX_LORA_STRENGTH = 4.0


@dataclass(frozen=True, slots=True)
class CustomLoraSpec:
    name: str
    strength: float = 1.0
    enabled: bool = True

    @property
    def key(self) -> tuple[str, float]:
        return self.name, round(float(self.strength), 6)


def _clamp_strength(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 1.0
    return max(MIN_LORA_STRENGTH, min(MAX_LORA_STRENGTH, number))


def normalize_custom_loras(value: Any) -> tuple[CustomLoraSpec, ...]:
    """Normalize the flexible Studio UI payload into a bounded ordered stack."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    specs: list[CustomLoraSpec] = []
    for item in value[:MAX_CUSTOM_LORAS]:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or item.get("lora") or "").strip().replace("\\", "/")
        if not name or name.lower() in {"none", "disabled", "off"}:
            continue
        enabled = item.get("enabled", True) is not False
        strength = _clamp_strength(item.get("strength", 1.0))
        if not enabled or abs(strength) < 1e-8:
            continue
        specs.append(CustomLoraSpec(name=name, strength=strength, enabled=True))
    return tuple(specs)


def _basename(value: str) -> str:
    return PurePosixPath(str(value).replace("\\", "/")).name.lower()


def resolve_custom_lora(choices: Iterable[str], requested: str) -> str:
    """Resolve an exact relative path, falling back only to an unambiguous basename."""

    values = sorted({str(value).replace("\\", "/") for value in choices if str(value).strip()}, key=str.lower)
    request = str(requested).replace("\\", "/").strip()
    exact = [value for value in values if value.lower() == request.lower()]
    if len(exact) == 1:
        return exact[0]
    requested_base = _basename(request)
    basename_matches = [value for value in values if _basename(value) == requested_base]
    if len(basename_matches) == 1:
        return basename_matches[0]
    if len(basename_matches) > 1:
        raise PDDBackendError(
            f"Custom LoRA {requested!r} is ambiguous because several files share that filename. "
            "Select the full relative path shown by H3 Studio."
        )
    raise PDDBackendError(
        f"Custom LoRA {requested!r} is not available in ComfyUI/models/loras. Refresh the Director LoRA list after "
        "adding the file."
    )


_STACK_LOCK = threading.RLock()
_STACK_CACHE_KEY: tuple[Any, ...] | None = None
_STACK_CACHE_VALUE: tuple[Any, str] | None = None


def clear_custom_lora_cache() -> None:
    global _STACK_CACHE_KEY, _STACK_CACHE_VALUE
    with _STACK_LOCK:
        _STACK_CACHE_KEY = None
        _STACK_CACHE_VALUE = None


def apply_custom_lora_stack(
    model: Any,
    specs: Sequence[CustomLoraSpec],
    *,
    reserved_artifacts: Iterable[str] = (),
) -> tuple[Any, str]:
    """Apply an ordered model-only LoRA stack using ComfyUI's bypass path.

    Bypass-forward is particularly important for H3's W4A8/INT8/FP8 models: a
    normal weight merge can materialize and requantize huge base tensors. The
    final patched model is cached as one bounded stack so seed/prompt reruns do
    not reload the LoRA files or recreate injection graphs.
    """

    active = tuple(spec for spec in specs if spec.enabled and abs(spec.strength) >= 1e-8)
    if not active:
        return model, "custom_loras=none"

    reserved = {_basename(value) for value in reserved_artifacts if str(value).strip()}
    duplicates = [spec.name for spec in active if _basename(spec.name) in reserved]
    if duplicates:
        joined = ", ".join(duplicates)
        raise PDDBackendError(
            f"Do not add the active acceleration adapter again as a custom LoRA ({joined}). "
            "The Speed profile already applies it at its verified strength."
        )

    cache_key = (id(model), tuple(spec.key for spec in active))
    global _STACK_CACHE_KEY, _STACK_CACHE_VALUE
    with _STACK_LOCK:
        if cache_key == _STACK_CACHE_KEY and _STACK_CACHE_VALUE is not None:
            cached_model, cached_info = _STACK_CACHE_VALUE
            LOGGER.info("[H3 Studio] Custom LoRA stack cache hit; reused %d adapter(s)", len(active))
            return cached_model, f"{cached_info} | custom_lora_cache=hit"

        import folder_paths
        import nodes

        choices = folder_paths.get_filename_list("loras")
        mappings = getattr(nodes, "NODE_CLASS_MAPPINGS", {})
        patched = model
        applied: list[str] = []
        backends: list[str] = []
        for spec in active:
            resolved = resolve_custom_lora(choices, spec.name)
            patched, backend = _load_model_lora(patched, resolved, spec.strength, mappings)
            applied.append(f"{resolved}@{spec.strength:g}")
            backends.append(backend)

        backend_label = "+".join(sorted(set(backends)))
        info = f"custom_loras={len(applied)} [{'; '.join(applied)}] | custom_lora_backend={backend_label}"
        _STACK_CACHE_KEY = cache_key
        _STACK_CACHE_VALUE = (patched, info)
        LOGGER.info("[H3 Studio] Applied custom LoRA stack: %s", info)
        return patched, info
