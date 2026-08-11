"""Small runtime guards for memory-constrained H3 generation paths.

These guards preserve optional analyzer/writer behavior for reference workflows
while preventing legacy saved state from staging a helper Qwen model before a
plain zero-image H3 text-to-image conditioning pass.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from .prompting import comfy_analyzer
from .references import ReferenceImage

LOGGER = logging.getLogger(__name__)

_ORIGINAL_ANALYZE_REFERENCES = comfy_analyzer.analyze_references


def _lean_analyze_references(
    clip: Any,
    prompt: str,
    references: Sequence[ReferenceImage],
    images: Sequence[Any],
    **kwargs,
):
    """Skip the optional prompt-writer model for zero-image T2I.

    alpha.12 allowed ``deep_enhancement`` to enter the Qwen helper path even
    when there were no reference images. On 32 GB hosts with model files in
    ``/dev/shm`` that can stage the 4B helper immediately before H3's 32B text
    encoder, recreating the host-memory pressure that the validated L4 path had
    avoided. Reference workflows still use the configured analyzer/writer.
    """

    if not images and kwargs.get("deep_enhancement"):
        LOGGER.info(
            "[H3 Studio] Zero-image T2I: skipping optional Qwen prompt writer to preserve H3 encoder memory"
        )
        return (
            tuple(references),
            str(prompt),
            "Image analysis: no references to inspect. "
            "Prompt writer skipped for zero-image T2I to preserve H3 encoder memory.",
        )
    return _ORIGINAL_ANALYZE_REFERENCES(clip, prompt, references, images, **kwargs)


def install_runtime_guards() -> None:
    """Install idempotent compatibility guards before ComfyUI executes nodes."""

    current = comfy_analyzer.analyze_references
    if bool(getattr(current, "__h3studio_zero_image_guard__", False)):
        return
    _lean_analyze_references.__h3studio_zero_image_guard__ = True
    comfy_analyzer.analyze_references = _lean_analyze_references
