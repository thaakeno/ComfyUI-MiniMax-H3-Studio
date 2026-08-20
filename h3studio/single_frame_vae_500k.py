"""MiniMax H3 single-frame VAE compatibility and safe decode defaults.

The iamkaikai 500K checkpoint is a decoder-focused training release. H3 Studio
supports complete ComfyUI conversions of that decoder through the existing T=1
image-VAE path while keeping the normal H3 video VAE untouched.
"""

from __future__ import annotations

import logging
import re
from contextlib import suppress
from typing import Any

LOGGER = logging.getLogger(__name__)

COMFY_500K_REPO = "https://huggingface.co/Alissonerdx/MiniMax-H3-Single-Frame-VAE-500K-Comfy"
ORIGINAL_500K_REPO = "https://huggingface.co/iamkaikai/MiniMax-H3-Single-Frame-VAE-500K"

_NATIVE_TILE = 256
_NATIVE_OVERLAP = 64
_SINGLE_FRAME_500K_TILE = 512
_SINGLE_FRAME_500K_OVERLAP = 64
_INSTALL_MARKER = "__h3studio_single_frame_vae_500k__"


def _compact(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def is_single_frame_image_vae(name: str | None) -> bool:
    """Return whether a filename looks like an H3 image-specialized VAE."""

    compact = _compact(name)
    if "minimaxh3" not in compact:
        return False
    return "imagevae" in compact or "t1" in compact or "singleframe" in compact


def is_single_frame_500k(name: str | None) -> bool:
    """Recognize iamkaikai's 500K line, including ComfyUI conversions/renames."""

    compact = _compact(name)
    return "minimaxh3" in compact and "singleframe" in compact and "500k" in compact


def is_obvious_decoder_only_500k(name: str | None) -> bool:
    """Reject the original decoder-only filename when it is clearly identifiable.

    The original training repo publishes decoder weights. H3 Studio's normal
    VAELoader path needs a complete ComfyUI VAE checkpoint. A converted file may
    still contain the word ``decoder``; ``comfy`` therefore takes precedence.
    """

    compact = _compact(name)
    return is_single_frame_500k(name) and "decoder" in compact and "comfy" not in compact


def image_vae_preference(name: str | None) -> tuple[int, str]:
    """Prefer the new Comfy 500K checkpoint while preserving legacy T=1 VAEs."""

    compact = _compact(name)
    if is_single_frame_500k(name) and "comfy" in compact:
        rank = 0
    elif is_single_frame_500k(name):
        rank = 1
    else:
        rank = 2
    return rank, str(name or "").lower()


def auto_tile_settings(name: str | None) -> tuple[int, int]:
    """Return the Auto spatial profile for a selected image VAE."""

    if is_single_frame_500k(name):
        return _SINGLE_FRAME_500K_TILE, _SINGLE_FRAME_500K_OVERLAP
    return _NATIVE_TILE, _NATIVE_OVERLAP


def mark_loaded_vae(vae: Any, name: str) -> Any:
    """Attach non-invasive runtime hints used by H3 Studio's decoder."""

    tile, overlap = auto_tile_settings(name)
    targets = (vae, getattr(vae, "first_stage_model", None))
    for target in targets:
        if target is None:
            continue
        with suppress(Exception):
            setattr(target, "_h3studio_image_vae_name", str(name))
            setattr(target, "_h3studio_auto_tile_size", int(tile))
            setattr(target, "_h3studio_auto_tile_overlap", int(overlap))
    return vae


def _friendly_500k_load_error(name: str, error: Exception) -> ValueError:
    return ValueError(
        "H3 Studio could not load the selected MiniMax H3 Single-Frame VAE 500K as a complete ComfyUI VAE. "
        "Use the ComfyUI-converted checkpoint from "
        f"{COMFY_500K_REPO} in ComfyUI/models/vae. The original iamkaikai training release at "
        f"{ORIGINAL_500K_REPO} contains decoder-focused weights and is not the checkpoint H3 Studio expects. "
        f"Selected file: {name}. Loader error: {type(error).__name__}: {error}"
    )


def _install_loader_support(loader_module: Any) -> None:
    if bool(getattr(loader_module, _INSTALL_MARKER, False)):
        return

    def image_vae_choices() -> list[str]:
        values = loader_module._filenames("vae")
        selected = [
            value
            for value in values
            if is_single_frame_image_vae(value) and not is_obvious_decoder_only_500k(value)
        ]
        selected.sort(key=image_vae_preference)
        return [loader_module.DISABLED_IMAGE_VAE, *selected]

    loader_module.image_vae_choices = image_vae_choices

    original_input_types = loader_module.H3StudioLoader.INPUT_TYPES

    @classmethod
    def input_types(cls):
        schema = original_input_types()
        choices = image_vae_choices()
        schema["required"]["image_vae"] = (
            choices,
            {
                "default": loader_module.DISABLED_IMAGE_VAE,
                "tooltip": (
                    "Optional single-frame H3 VAE. MiniMax H3 Single-Frame VAE 500K Comfy is preferred when "
                    "installed; legacy Mamad8 T=1 checkpoints remain supported. Image-only and never replaces "
                    "the normal H3 video VAE."
                ),
            },
        )
        return schema

    loader_module.H3StudioLoader.INPUT_TYPES = input_types

    def image_vae_for_decode(self):
        name = str(self.image_vae_name or "")
        if not name:
            raise ValueError(
                "Select a MiniMax H3 single-frame Image VAE in H3 Studio Loader, or use the normal 5-frame decoder."
            )
        if is_obvious_decoder_only_500k(name):
            raise _friendly_500k_load_error(name, ValueError("decoder-only checkpoint selected"))

        with self._lock:
            if self.image_vae is None:
                LOGGER.info("[H3 Studio] Loading optional single-frame image VAE=%s", name)
                try:
                    loaded = loader_module._load_vae(name)
                except Exception as error:
                    if is_single_frame_500k(name):
                        raise _friendly_500k_load_error(name, error) from error
                    raise
                self.image_vae = mark_loaded_vae(loaded, name)
                tile, overlap = auto_tile_settings(name)
                LOGGER.info(
                    "[H3 Studio] Image VAE ready: %s | auto spatial profile=%d/%d",
                    name,
                    tile,
                    overlap,
                )
            return self.image_vae

    loader_module.H3StudioBundle.image_vae_for_decode = image_vae_for_decode
    setattr(loader_module, _INSTALL_MARKER, True)


def _install_decode_support(decode_module: Any) -> None:
    if bool(getattr(decode_module, _INSTALL_MARKER, False)):
        return

    original_resolve = decode_module._resolve_spatial_settings

    def resolve_spatial_settings(model: Any, mode: str, tile_size: int, overlap: int) -> tuple[int, int]:
        if str(mode).lower() == "manual":
            return original_resolve(model, mode, tile_size, overlap)
        hinted_tile = getattr(model, "_h3studio_auto_tile_size", None)
        hinted_overlap = getattr(model, "_h3studio_auto_tile_overlap", None)
        if hinted_tile is not None and hinted_overlap is not None:
            ratio = max(1, int(getattr(model, "vae_ratio", 16) or 16))
            tile = decode_module._aligned(int(hinted_tile), ratio, minimum=ratio * 8)
            overlap_value = decode_module._aligned(int(hinted_overlap), ratio, minimum=ratio)
            return tile, min(overlap_value, tile - ratio)
        return original_resolve(model, mode, tile_size, overlap)

    decode_module._resolve_spatial_settings = resolve_spatial_settings

    original_decode = decode_module.H3StudioDecode.decode

    def decode_with_500k_oom_fallback(
        self,
        samples,
        vae,
        tiling_mode: str = "Auto",
        tile_size: int = 256,
        tile_overlap: int = 64,
        tile_batch: str = "Auto",
        unique_id=None,
    ):
        first_stage = getattr(vae, "first_stage_model", None)
        name = str(
            getattr(first_stage, "_h3studio_image_vae_name", "")
            or getattr(vae, "_h3studio_image_vae_name", "")
        )
        use_500k_auto = str(tiling_mode).lower() != "manual" and is_single_frame_500k(name)
        try:
            return original_decode(
                self,
                samples,
                vae,
                tiling_mode=tiling_mode,
                tile_size=tile_size,
                tile_overlap=tile_overlap,
                tile_batch=tile_batch,
                unique_id=unique_id,
            )
        except Exception as error:
            if not use_500k_auto or not decode_module.comfy.model_management.is_oom(error):
                raise
            LOGGER.warning(
                "[H3 Studio - Decode] 500K single-frame VAE Auto 512/64 exceeded VRAM; retrying once at 256/64."
            )
            with suppress(Exception):
                decode_module.comfy.model_management.soft_empty_cache()
            return original_decode(
                self,
                samples,
                vae,
                tiling_mode="Manual",
                tile_size=_NATIVE_TILE,
                tile_overlap=_NATIVE_OVERLAP,
                tile_batch=tile_batch,
                unique_id=unique_id,
            )

    decode_module.H3StudioDecode.decode = decode_with_500k_oom_fallback
    decode_module.H3StudioDecode.DESCRIPTION = (
        "Decode MiniMax H3 with native spatial tiling and OOM-safe batching. Auto keeps the normal H3 256/64 "
        "geometry, uses the 500K single-frame VAE's 512/64 still-image profile when selected, and retries at "
        "256/64 if that larger profile exceeds VRAM. Manual settings always remain authoritative."
    )

    original_decode_input_types = decode_module.H3StudioDecode.INPUT_TYPES

    @classmethod
    def decode_input_types(cls):
        schema = original_decode_input_types()
        schema["optional"]["tiling_mode"][1]["tooltip"] = (
            "Auto uses 256/64 for the normal H3 video/legacy image VAE and the 500K single-frame VAE profile "
            "when detected, with one safe 256/64 retry on OOM. Manual enables explicit tile geometry."
        )
        return schema

    decode_module.H3StudioDecode.INPUT_TYPES = decode_input_types
    setattr(decode_module, _INSTALL_MARKER, True)


def install() -> None:
    """Install 500K support after H3 Studio's loader and decoder are registered."""

    from .nodes import decode as decode_module
    from .nodes import loader as loader_module

    _install_loader_support(loader_module)
    _install_decode_support(decode_module)


__all__ = [
    "COMFY_500K_REPO",
    "ORIGINAL_500K_REPO",
    "auto_tile_settings",
    "image_vae_preference",
    "install",
    "is_obvious_decoder_only_500k",
    "is_single_frame_500k",
    "is_single_frame_image_vae",
    "mark_loaded_vae",
]
