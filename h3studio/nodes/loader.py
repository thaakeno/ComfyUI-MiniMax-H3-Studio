"""Lazy H3 model bundle loader.

Only one transformer is retained by the bundle at a time. Switching between
FL2VA and REF2VA releases the previous model before loading the other path.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

import folder_paths
import nodes

try:
    import comfy.model_management
except Exception:  # pragma: no cover - ComfyUI always provides this at runtime
    comfy = None

NONE_MODEL = "None"
_WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin")
_H3_TOKENS = ("minimax", "h3", "fl2va", "ref2va")
LOGGER = logging.getLogger(__name__)


def _normalize(name: str) -> str:
    return str(name or "").replace("\\", "/").strip()


def _compact(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize(name).lower())


def _is_h3(name: str) -> bool:
    compact = _compact(name)
    return "minimaxh3" in compact or ("h3" in compact and any(token in compact for token in ("fl2va", "ref2va")))


def _is_ref(name: str) -> bool:
    return "ref2va" in _compact(name) or "reference" in _compact(name)


def _is_fl(name: str) -> bool:
    compact = _compact(name)
    return "fl2va" in compact or ("h3" in compact and "ref2va" not in compact)


def _is_none(value: str | None) -> bool:
    return not value or str(value).strip().lower() in {"none", "null", "disabled", "off"}


def _filenames(*categories: str) -> list[str]:
    values: list[str] = []
    for category in categories:
        try:
            values.extend(folder_paths.get_filename_list(category))
        except Exception:
            continue
    return sorted(set(_normalize(value) for value in values if _normalize(value)), key=str.lower)


def _filtered(values: Iterable[str], predicate, fallback: str) -> list[str]:
    values = list(values)
    selected = [value for value in values if predicate(value)]
    return selected or (values if values else [fallback])


def fl2va_choices() -> list[str]:
    values = _filenames("diffusion_models", "unet")
    return [NONE_MODEL] + _filtered(values, lambda value: _is_h3(value) and _is_fl(value), "minimax_h3_fl2va.safetensors")


def ref2va_choices() -> list[str]:
    values = _filenames("diffusion_models", "unet")
    return [NONE_MODEL] + _filtered(values, lambda value: _is_h3(value) and _is_ref(value), "minimax_h3_ref2va.safetensors")


def clip_choices() -> list[str]:
    values = _filenames("text_encoders", "clip")
    return _filtered(
        values,
        lambda value: "qwen3vl" in _compact(value) and ("minimax" in _compact(value) or "h3" in _compact(value)),
        "qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
    )


def vae_choices() -> list[str]:
    values = _filenames("vae")
    return _filtered(values, lambda value: "minimaxh3video" in _compact(value), "minimax_h3_video_vae_fp16.safetensors")


def _registered_class(*names: str):
    mappings = getattr(nodes, "NODE_CLASS_MAPPINGS", {})
    for name in names:
        candidate = mappings.get(name)
        if candidate is not None:
            return candidate
    return None


def _load_unet(name: str):
    if _normalize(name).lower().endswith(".gguf"):
        loader_class = _registered_class("UnetLoaderGGUF", "UNETLoaderGGUF", "UnetLoaderGGUFAdvanced")
        if loader_class is None:
            raise ValueError("The selected GGUF transformer requires ComfyUI-GGUF.")
        loader = loader_class()
        for method_name in ("load_unet", "load_model", "load"):
            method = getattr(loader, method_name, None)
            if method:
                result = method(name)
                return result[0] if isinstance(result, tuple) else result
        raise ValueError("Installed ComfyUI-GGUF loader does not expose a compatible model-loading method.")
    result = nodes.UNETLoader().load_unet(name, "default")
    return result[0]


def _load_clip(name: str):
    loader = nodes.CLIPLoader()
    try:
        return loader.load_clip(name, "minimax")[0]
    except TypeError:
        return loader.load_clip(name, type="minimax")[0]


def _load_vae(name: str):
    return nodes.VAELoader().load_vae(name)[0]


@dataclass(slots=True)
class H3StudioBundle:
    fl2va_name: str
    ref2va_name: str
    clip_name: str
    video_vae_name: str
    clip: Any
    video_vae: Any
    _model: Any = field(default=None, init=False, repr=False)
    _model_name: str = field(default="", init=False, repr=False)
    _model_kind: str = field(default="", init=False, repr=False)
    _lock: Any = field(default_factory=threading.RLock, init=False, repr=False)

    def selected_name(self, kind: str) -> str:
        preferred = self.ref2va_name if kind == "ref2va" else self.fl2va_name
        fallback = self.fl2va_name if kind == "ref2va" else self.ref2va_name
        if not _is_none(preferred):
            return preferred
        if not _is_none(fallback):
            return fallback
        raise ValueError("Select at least one H3 transformer in H3 Studio Loader.")

    def model_for(self, kind: str):
        kind = "ref2va" if kind == "ref2va" else "fl2va"
        name = self.selected_name(kind)
        with self._lock:
            if self._model is not None and self._model_name == name:
                return self._model
            self.release_model()
            LOGGER.info("[H3 Studio] Loading transformer route=%s model=%s", kind, name)
            self._model = _load_unet(name)
            self._model_name = name
            self._model_kind = kind
            return self._model

    def release_model(self) -> None:
        with self._lock:
            self._model = None
            self._model_name = ""
            self._model_kind = ""
            with suppress(Exception):
                comfy.model_management.soft_empty_cache()

    def summary(self) -> str:
        return (
            f"FL2VA={self.fl2va_name} | REF2VA={self.ref2va_name} | "
            f"CLIP={self.clip_name} | Video VAE={self.video_vae_name}"
        )


class H3StudioLoader:
    CATEGORY = "H3 Studio"
    FUNCTION = "load"
    RETURN_TYPES = ("H3_STUDIO_BUNDLE", "CLIP", "VAE", "STRING")
    RETURN_NAMES = ("h3_bundle", "clip", "video_vae", "model_info")
    DESCRIPTION = "Load H3's Qwen3-VL encoder and video VAE, with lazy FL2VA/REF2VA transformer switching."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "fl2va_model": (fl2va_choices(), {"default": next((v for v in fl2va_choices() if v != NONE_MODEL), NONE_MODEL)}),
                "ref2va_model": (ref2va_choices(), {"default": next((v for v in ref2va_choices() if v != NONE_MODEL), NONE_MODEL)}),
                "text_encoder": (clip_choices(),),
                "video_vae": (vae_choices(),),
            }
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return "|".join(str(kwargs.get(key, "")) for key in ("fl2va_model", "ref2va_model", "text_encoder", "video_vae"))

    @staticmethod
    def load(fl2va_model: str, ref2va_model: str, text_encoder: str, video_vae: str):
        if _is_none(fl2va_model) and _is_none(ref2va_model):
            raise ValueError("Select at least one MiniMax H3 transformer: FL2VA or REF2VA.")
        clip = _load_clip(text_encoder)
        vae = _load_vae(video_vae)
        bundle = H3StudioBundle(fl2va_model, ref2va_model, text_encoder, video_vae, clip, vae)
        LOGGER.info("\n[H3 Studio] Model bundle\n  %s", bundle.summary())
        return bundle, clip, vae, bundle.summary()
