"""L4 conditioning policy: isolate the 32B text encoder, keep hot diffusion reruns.

The healthy L4 benchmark came from treating H3 as three sequential stages rather
than letting two giant DynamicVRAM models overlap. On a prompt-cache miss we:

1. release any hot diffusion patcher/clones from the previous generation,
2. fully stage the 32B text encoder for one encode,
3. cache the resulting conditioning,
4. completely release the text encoder before diffusion starts.

On a prompt-cache hit none of those operations run. That is intentional: a
seed-only rerun can keep the H3 transformer hot and go straight back to sampling.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Hashable
from contextlib import suppress
from typing import Any

from .runtime_handoff import release_stage_patcher

LOGGER = logging.getLogger(__name__)
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


def _force_full_text_encoder(patcher: Any) -> tuple[str, float]:
    if patcher is None:
        return "unavailable", 0.0

    import comfy.model_management as mm

    started = time.perf_counter()
    try:
        # This is the exact policy that produced the healthy ~19 s L4
        # conditioning miss: materialize the isolated 32B encoder once instead
        # of streaming its quantized layers block-by-block through DynamicVRAM.
        mm.load_models_gpu([patcher], force_full_load=True)
        _sync_cuda_for(patcher)
        return "full", time.perf_counter() - started
    except Exception as exc:
        elapsed = time.perf_counter() - started
        LOGGER.warning(
            "[H3 Studio] Full text-encoder staging unavailable after %.2fs (%s); falling back to native DynamicVRAM.",
            elapsed,
            type(exc).__name__,
        )
        _soft_empty_cache()
        return f"dynamic-fallback:{type(exc).__name__}", elapsed


def _release_text_encoder(patcher: Any) -> str:
    result = release_stage_patcher(patcher, label="text_encoder")
    # Comfy's async offload path can retain a large pinned staging pool unless
    # the manager gets a cache-clean opportunity after the targeted unload.
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
            # Crucial warm path: do not touch model-manager state. The diffusion
            # transformer from the previous seed-only run is allowed to stay hot.
            return cached, "HIT", 0.0, "warm-cache; diffusion=keep-hot"

        started = time.perf_counter()
        diffusion_release = _release_previous_diffusion(bundle)
        tokens = build_tokens()
        tokenized = time.perf_counter()

        patcher = getattr(getattr(bundle, "clip", None), "patcher", None)
        residency_mode, load_seconds = _force_full_text_encoder(patcher)
        encode_started = time.perf_counter()
        try:
            conditioning = bundle.clip.encode_from_tokens_scheduled(tokens)
        finally:
            text_release = _release_text_encoder(patcher)
        encode_finished = time.perf_counter()

        conditioning_cache._PROMPT_CACHE.put(key, conditioning)
        finished = time.perf_counter()
        tokenize_seconds = tokenized - started
        encode_seconds = encode_finished - encode_started
        runtime = (
            f"isolated-text-encoder; residency={residency_mode}; load={load_seconds:.3f}s; "
            f"tokenize={tokenize_seconds:.3f}s; encode={encode_seconds:.3f}s; "
            f"{diffusion_release}; {text_release}"
        )
        return conditioning, "MISS", finished - started, runtime

    isolated_encode_prompt.__h3studio_isolated_text_fastpath__ = True
    conditioning_cache._encode_prompt = isolated_encode_prompt
    _INSTALLED = True


__all__ = ["install_conditioning_fastpath"]
