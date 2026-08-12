"""Restore the native H3 conditioning path that produced the healthy L4 baseline.

The prompt cache remains unchanged. On a cache miss ComfyUI owns the 32B text
encoder load/encode lifecycle; Studio does not synchronously unload the 15 GiB
patcher immediately after encode. The following diffusion request lets Comfy's
manager reclaim what it needs while preserving its DynamicVRAM/pinned-memory
state. Cache hits remain zero-work.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Hashable
from typing import Any

_INSTALLED = False


def install_conditioning_fastpath() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from . import conditioning_cache

    def native_encode_prompt(bundle: Any, key: Hashable, build_tokens: Callable[[], Any]):
        cached = conditioning_cache._PROMPT_CACHE.get(key)
        if cached is not None:
            return cached, "HIT", 0.0, "warm-cache"

        started = time.perf_counter()
        tokens = build_tokens()
        tokenized = time.perf_counter()
        conditioning = bundle.clip.encode_from_tokens_scheduled(tokens)
        finished = time.perf_counter()
        conditioning_cache._PROMPT_CACHE.put(key, conditioning)

        tokenize_seconds = tokenized - started
        encode_seconds = finished - tokenized
        runtime = f"native-comfy-manager; tokenize={tokenize_seconds:.3f}s; encode={encode_seconds:.3f}s"
        return conditioning, "MISS", finished - started, runtime

    native_encode_prompt.__h3studio_proven_native_fastpath__ = True
    conditioning_cache._encode_prompt = native_encode_prompt
    _INSTALLED = True


__all__ = ["install_conditioning_fastpath"]
