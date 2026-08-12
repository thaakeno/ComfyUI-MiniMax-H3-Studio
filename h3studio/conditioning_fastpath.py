"""L4 conditioning policy: one scheduled text-encoder load, hot diffusion reruns.

On a prompt-cache miss Studio owns only the stage boundaries:

1. release any hot diffusion patcher/clones from the previous generation,
2. tokenize,
3. let ComfyUI's scheduled CLIP encode perform the one text-encoder load it
   already owns,
4. cache the conditioning and completely release the text encoder before
   diffusion starts.

Do not pre-load the 32B encoder here. CLIP.encode_from_tokens_scheduled() enters
CLIP.encode_from_tokens(), which calls CLIP.load_model() and therefore
model_management.load_models_gpu() itself. Pre-loading it separately duplicates
the giant H3 encoder staging/read on DynamicVRAM systems.

On a prompt-cache hit none of those operations run so seed-only reruns can keep
the H3 transformer hot and go straight back to sampling.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Hashable
from contextlib import suppress
from typing import Any

from .runtime_handoff import release_stage_patcher

_INSTALLED = False


def _sync_cuda_for(patcher: Any) -> None:
    with suppress(Exception):
        import comfy.model_management as mm
        import torch

        device = getattr(patcher, "load_device", None) or mm.get_torch_device()
        if torch.cuda.is_available() and getattr(device, "type", "") == "cuda":
            torch.cuda.synchronize(device)


def _soft_empty_cache() -> None:
    with suppress(Exception):
        import comfy.model_management as mm

        mm.soft_empty_cache()


def _release_previous_diffusion(bundle: Any) -> str:
    """Clear the previous hot H3 model only when a new text encode is required."""

    patcher = getattr(bundle, "_model", None)
    if patcher is None:
        return "pre_text_diffusion=none"
    result = release_stage_patcher(patcher, label="pre_text_diffusion")
    _soft_empty_cache()
    _sync_cuda_for(patcher)
    return result.summary()


def _release_text_encoder(patcher: Any) -> str:
    result = release_stage_patcher(patcher, label="text_encoder")
    # Give Comfy's async offload path a cache-clean opportunity after the
    # targeted unload so a completed TE stage cannot poison the next H3 stage.
    _soft_empty_cache()
    _sync_cuda_for(patcher)
    return result.summary()


def install_conditioning_fastpath() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from . import conditioning_cache

    def isolated_encode_prompt(bundle: Any, key: Hashable, build_tokens: Callable[[], Any]):
        cached = conditioning_cache._PROMPT_CACHE.get(key)
        if cached is not None:
            # Zero-work warm path: leave the previous diffusion residency alone.
            return cached, "HIT", 0.0, "warm-cache; diffusion=keep-hot"

        started = time.perf_counter()
        diffusion_release = _release_previous_diffusion(bundle)
        tokens = build_tokens()
        tokenized = time.perf_counter()

        patcher = getattr(getattr(bundle, "clip", None), "patcher", None)
        encode_started = time.perf_counter()
        encoded = encode_started
        try:
            # IMPORTANT: this is the single TE load owner. ComfyUI's CLIP
            # scheduled encode calls CLIP.load_model() internally. Do not call
            # model_management.load_models_gpu() before this.
            conditioning = bundle.clip.encode_from_tokens_scheduled(tokens)
            _sync_cuda_for(patcher)
            encoded = time.perf_counter()
        finally:
            text_release = _release_text_encoder(patcher)

        conditioning_cache._PROMPT_CACHE.put(key, conditioning)
        finished = time.perf_counter()
        tokenize_seconds = tokenized - started
        encode_seconds = encoded - encode_started
        release_seconds = finished - encoded
        runtime = (
            f"single-scheduled-text-encode; tokenize={tokenize_seconds:.3f}s; "
            f"encode={encode_seconds:.3f}s; release={release_seconds:.3f}s; "
            f"{diffusion_release}; {text_release}"
        )
        return conditioning, "MISS", finished - started, runtime

    isolated_encode_prompt.__h3studio_isolated_text_fastpath__ = True
    conditioning_cache._encode_prompt = isolated_encode_prompt
    _INSTALLED = True


__all__ = ["install_conditioning_fastpath"]
