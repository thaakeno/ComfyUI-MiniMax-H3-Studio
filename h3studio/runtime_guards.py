"""Runtime memory guards for optional Qwen helper models.

Prompt enhancement must honor the Director toggle and selected Loader model.
When it runs, release the optional analyzer/writer objects immediately after the
analysis/writer pass so H3's 32B conditioning encoder does not compete with a
resident helper model on memory-constrained hosts.
"""

from __future__ import annotations

import gc
import logging
from contextlib import suppress

from .prompting import comfy_analyzer

LOGGER = logging.getLogger(__name__)

_ORIGINAL_ANALYZE_REFERENCES = comfy_analyzer.analyze_references


def _helper_bundle(*loaders):
    for loader in loaders:
        owner = getattr(loader, "__self__", None)
        if owner is not None and hasattr(owner, "analyzer_clip") and hasattr(owner, "prompt_writer_clip"):
            return owner
    return None


def _release_optional_helpers(bundle) -> None:
    if bundle is None:
        return
    analyzer = getattr(bundle, "analyzer_clip", None)
    writer = getattr(bundle, "prompt_writer_clip", None)
    if analyzer is None and writer is None:
        return

    bundle.analyzer_clip = None
    bundle.prompt_writer_clip = None
    del analyzer, writer
    gc.collect()

    # Comfy's loaded-model registry keeps weak references to model patchers.
    # Once Studio drops the helper CLIP objects, ask Comfy to prune dead entries.
    # Do not manually unload the H3 encoder/transformer or alter DynamicVRAM.
    with suppress(Exception):
        import comfy.model_management

        comfy.model_management.cleanup_models_gc()

    LOGGER.info("[H3 Studio] Released optional Qwen analyzer/writer before H3 conditioning")


def _memory_safe_analyze_references(clip, prompt, references, images, **kwargs):
    """Run the configured helper normally, then release it before H3 encode."""

    bundle = _helper_bundle(kwargs.get("writer_loader"), kwargs.get("clip_loader"))
    try:
        return _ORIGINAL_ANALYZE_REFERENCES(clip, prompt, references, images, **kwargs)
    finally:
        _release_optional_helpers(bundle)


def install_runtime_guards() -> None:
    """Install the idempotent helper-release guard before ComfyUI executes nodes."""

    current = comfy_analyzer.analyze_references
    if bool(getattr(current, "__h3studio_helper_release_guard__", False)):
        return
    _memory_safe_analyze_references.__h3studio_helper_release_guard__ = True
    comfy_analyzer.analyze_references = _memory_safe_analyze_references
