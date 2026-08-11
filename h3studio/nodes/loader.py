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

from ..vae_io import detect_vae_io

try:
    import comfy.model_management
except Exception:  # pragma: no cover - ComfyUI always provides this at runtime
    comfy = None

NONE_MODEL = "None"
AUTO_ANALYZER = "Auto · Qwen3-VL 4B"
DISABLED_ANALYZER = "Disabled"
SAME_AS_ANALYZER = "Same as image analyzer"
DISABLED_IMAGE_VAE = "Disabled - original H3 video VAE only"
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
    return [NONE_MODEL] + _filtered(
        values, lambda value: _is_h3(value) and _is_fl(value), "minimax_h3_fl2va.safetensors"
    )


def ref2va_choices() -> list[str]:
    values = _filenames("diffusion_models", "unet")
    return [NONE_MODEL] + _filtered(
        values, lambda value: _is_h3(value) and _is_ref(value), "minimax_h3_ref2va.safetensors"
    )


def clip_choices() -> list[str]:
    values = _filenames("text_encoders", "clip")
    return _filtered(
        values,
        lambda value: "qwen3vl" in _compact(value) and ("minimax" in _compact(value) or "h3" in _compact(value)),
        "qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
    )


def analyzer_choices() -> list[str]:
    values = _filenames("text_encoders", "clip")
    selected = [
        value
        for value in values
        if "qwen3vl" in _compact(value) and "minimax" not in _compact(value) and "h3" not in _compact(value)
    ]
    return [AUTO_ANALYZER, DISABLED_ANALYZER, *selected]


def prompt_writer_choices() -> list[str]:
    """Full Qwen3-VL checkpoints that retain a language-model head."""

    return [SAME_AS_ANALYZER, DISABLED_ANALYZER, *analyzer_choices()[2:]]


def _resolve_analyzer(name: str) -> str | None:
    if name == DISABLED_ANALYZER or _is_none(name):
        return None
    values = analyzer_choices()[2:]
    if name != AUTO_ANALYZER:
        return name
    preferred = next((value for value in values if "qwen3vl4bfp8scaled" in _compact(value)), None)
    return preferred or next((value for value in values if "qwen3vl4b" in _compact(value)), None)


def _resolve_prompt_writer(name: str, analyzer_name: str | None) -> str | None:
    if name == SAME_AS_ANALYZER:
        return analyzer_name
    if name == DISABLED_ANALYZER or _is_none(name):
        return None
    return name


def vae_choices() -> list[str]:
    values = _filenames("vae")
    return _filtered(values, lambda value: "minimaxh3video" in _compact(value), "minimax_h3_video_vae_fp16.safetensors")


def image_vae_choices() -> list[str]:
    """Experimental T=1 image-specialized H3 decoders."""

    values = _filenames("vae")
    selected = [
        value
        for value in values
        if "minimaxh3" in _compact(value) and ("imagevae" in _compact(value) or "t1" in _compact(value))
    ]
    return [DISABLED_IMAGE_VAE, *selected]


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


def _load_analyzer_clip(name: str):
    loader = nodes.CLIPLoader()
    try:
        return loader.load_clip(name, "krea2")[0]
    except TypeError:
        return loader.load_clip(name, type="krea2")[0]


def _load_vae(name: str):
    return nodes.VAELoader().load_vae(name)[0]


@dataclass(slots=True)
class H3StudioBundle:
    fl2va_name: str
    ref2va_name: str
    clip_name: str
    video_vae_name: str
    image_vae_name: str | None
    analyzer_name: str | None
    prompt_writer_name: str | None
    clip: Any
    video_vae: Any
    analyzer_clip: Any = None
    prompt_writer_clip: Any = None
    image_vae: Any = None
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

    def analyzer_for_analysis(self):
        if not self.analyzer_name:
            return None
        with self._lock:
            if self.analyzer_clip is None:
                LOGGER.info("[H3 Studio] Loading visual analyzer=%s", self.analyzer_name)
                self.analyzer_clip = _load_analyzer_clip(self.analyzer_name)
            return self.analyzer_clip

    def writer_for_enhancement(self):
        if not self.prompt_writer_name:
            return None
        if self.prompt_writer_name == self.analyzer_name:
            return self.analyzer_for_analysis()
        with self._lock:
            if self.prompt_writer_clip is None:
                LOGGER.info("[H3 Studio] Loading text-only prompt writer=%s", self.prompt_writer_name)
                self.prompt_writer_clip = _load_analyzer_clip(self.prompt_writer_name)
            return self.prompt_writer_clip

    def image_vae_for_decode(self):
        if not self.image_vae_name:
            raise ValueError(
                "Select Mamad8's experimental MiniMax H3 Image VAE in H3 Studio Loader, or use the normal 5-frame decoder."
            )
        with self._lock:
            if self.image_vae is None:
                LOGGER.info("[H3 Studio] Loading optional T=1 image VAE=%s", self.image_vae_name)
                self.image_vae = _load_vae(self.image_vae_name)
            return self.image_vae

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
        vae_io = detect_vae_io(self.video_vae)
        return (
            f"FL2VA={self.fl2va_name} | REF2VA={self.ref2va_name} | "
            f"CLIP={self.clip_name} | Video VAE={self.video_vae_name} | "
            f"Image VAE={self.image_vae_name or 'disabled'} | "
            f"Image analyzer={self.analyzer_name or 'disabled/missing'} | "
            f"Prompt writer={self.prompt_writer_name or 'disabled/missing'} | VAE I/O={vae_io.label}"
        )


class H3StudioLoader:
    CATEGORY = "H3 Studio"
    FUNCTION = "load"
    RETURN_TYPES = ("H3_STUDIO_BUNDLE", "CLIP", "VAE", "STRING")
    RETURN_NAMES = ("h3_bundle", "clip", "video_vae", "model_info")
    DESCRIPTION = (
        "Load H3's conditioning encoder and VAE, plus optional full Qwen3-VL models for cached pixel analysis "
        "and the text-only detailed prompt-director pass. The prompt writer defaults to reusing the analyzer."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "fl2va_model": (
                    fl2va_choices(),
                    {"default": next((v for v in fl2va_choices() if v != NONE_MODEL), NONE_MODEL)},
                ),
                "ref2va_model": (
                    ref2va_choices(),
                    {"default": next((v for v in ref2va_choices() if v != NONE_MODEL), NONE_MODEL)},
                ),
                "text_encoder": (clip_choices(),),
                "video_vae": (vae_choices(),),
                "image_vae": (
                    image_vae_choices(),
                    {
                        "default": DISABLED_IMAGE_VAE,
                        "tooltip": "Optional Mamad8 T=1 image decoder. Experimental and image-only; never replaces the normal H3 video VAE.",
                    },
                ),
                "image_analyzer": (analyzer_choices(), {"default": AUTO_ANALYZER}),
                "prompt_writer": (
                    prompt_writer_choices(),
                    {
                        "default": SAME_AS_ANALYZER,
                        "tooltip": "Reuses the 4B image analyzer by default. Select a full Qwen3-VL 8B checkpoint for stronger detailed rewrites, or disable the second pass.",
                    },
                ),
            }
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return "|".join(
            str(kwargs.get(key, ""))
            for key in (
                "fl2va_model",
                "ref2va_model",
                "text_encoder",
                "video_vae",
                "image_vae",
                "image_analyzer",
                "prompt_writer",
            )
        )

    @staticmethod
    def load(
        fl2va_model: str,
        ref2va_model: str,
        text_encoder: str,
        video_vae: str,
        image_vae: str = DISABLED_IMAGE_VAE,
        image_analyzer: str = AUTO_ANALYZER,
        prompt_writer: str = SAME_AS_ANALYZER,
    ):
        if _is_none(fl2va_model) and _is_none(ref2va_model):
            raise ValueError("Select at least one MiniMax H3 transformer: FL2VA or REF2VA.")
        clip = _load_clip(text_encoder)
        vae = _load_vae(video_vae)
        analyzer_name = _resolve_analyzer(image_analyzer)
        prompt_writer_name = _resolve_prompt_writer(prompt_writer, analyzer_name)
        bundle = H3StudioBundle(
            fl2va_name=fl2va_model,
            ref2va_name=ref2va_model,
            clip_name=text_encoder,
            video_vae_name=video_vae,
            image_vae_name=None if image_vae == DISABLED_IMAGE_VAE or _is_none(image_vae) else image_vae,
            analyzer_name=analyzer_name,
            prompt_writer_name=prompt_writer_name,
            clip=clip,
            video_vae=vae,
        )
        vae_io = detect_vae_io(vae)
        if vae_io.chunked:
            LOGGER.info("[H3 Studio] %s", vae_io.detail)
        else:
            LOGGER.warning("[H3 Studio] %s", vae_io.detail)
        LOGGER.info("\n[H3 Studio] Model bundle\n  %s", bundle.summary())
        return bundle, clip, vae, bundle.summary()
