"""Feature detection for ComfyUI's output-identical MiniMax H3 VAE I/O path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

UPSTREAM_H3_VAE_PR = "https://github.com/Comfy-Org/ComfyUI/pull/15446"
UPSTREAM_H3_VAE_MERGE = "2a68ce33b4c9ea6ee4283e618a74560cefb32694"


@dataclass(frozen=True, slots=True)
class VAEIOStatus:
    chunked: bool
    label: str
    detail: str


def detect_vae_io(vae: Any) -> VAEIOStatus:
    """Report the native ComfyUI VAE path without wrapping encode or decode."""

    first_stage = getattr(vae, "first_stage_model", None)
    if bool(getattr(first_stage, "comfy_has_chunked_io", False)):
        return VAEIOStatus(
            chunked=True,
            label="upstream chunked H3 VAE I/O",
            detail="ComfyUI comfy_has_chunked_io active; output buffers are owned by the native VAE wrapper",
        )
    return VAEIOStatus(
        chunked=False,
        label="legacy ComfyUI VAE I/O",
        detail=(
            "comfy_has_chunked_io unavailable; update to a ComfyUI build containing PR #15446 "
            f"({UPSTREAM_H3_VAE_MERGE[:12]}) for lower peak H3 VAE memory"
        ),
    )
