"""ComfyUI registration surface for the L4-stable H3 runtime.

The sampler/decode classes stay on the proven stable runtime. Conditioning uses
the native no-extra-unload fast path, and live preview keeps its decoder off
CUDA while dropping stale queued frames. Automatic fast-disk is disabled: on
Lightning persistent storage it can turn DynamicVRAM faults into storage-bound
inference. Users can still opt into ComfyUI --fast-disk explicitly.
"""

from __future__ import annotations

import os

from .conditioning_fastpath import install_conditioning_fastpath
from .nodes.benchmark import NODE_CLASS_MAPPINGS as BENCHMARK_NODE_CLASS_MAPPINGS
from .nodes.benchmark import NODE_DISPLAY_NAME_MAPPINGS as BENCHMARK_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.comparison import NODE_CLASS_MAPPINGS as COMPARISON_NODE_CLASS_MAPPINGS
from .nodes.comparison import NODE_DISPLAY_NAME_MAPPINGS as COMPARISON_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.director import (
    H3StudioCondition,
    H3StudioContextInspector,
    H3StudioDirector,
    H3StudioOutput,
)
from .nodes.image_runtime import NODE_CLASS_MAPPINGS as IMAGE_NODE_CLASS_MAPPINGS
from .nodes.image_runtime import NODE_DISPLAY_NAME_MAPPINGS as IMAGE_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.performance import H3StudioOptimizedLoader
from .nodes.save import NODE_CLASS_MAPPINGS as SAVE_NODE_CLASS_MAPPINGS
from .nodes.save import NODE_DISPLAY_NAME_MAPPINGS as SAVE_NODE_DISPLAY_NAME_MAPPINGS
from .preview_runtime_v4 import H3StudioTAEH3PreviewV4
from .runtime_guards import install_runtime_guards
from .runtime_stability import install_runtime_stability, runtime_node_classes
from .web_routes import register_routes

# Do not silently enable ComfyUI's disk-backed DynamicVRAM path merely because
# host RAM is below 48 GiB. Normal RAM/pinned-memory behavior is the safe default
# on Lightning; --fast-disk remains available as an explicit launcher choice.
os.environ.setdefault("H3STUDIO_DISABLE_AUTO_FAST_DISK", "1")

# Install this before runtime diagnostics wrap _encode_prompt so diagnostics
# observe the same native path that produced the healthy L4 conditioning run.
install_conditioning_fastpath()
install_runtime_guards()
install_runtime_stability()
register_routes()

H3StudioStableContextSamplingPreset, H3StudioStableDecode = runtime_node_classes()

NODE_CLASS_MAPPINGS = {
    "H3StudioDirector": H3StudioDirector,
    "H3StudioCondition": H3StudioCondition,
    "H3StudioOutput": H3StudioOutput,
    "H3StudioContextInspector": H3StudioContextInspector,
    "H3StudioTAEH3Preview": H3StudioTAEH3PreviewV4,
    **BENCHMARK_NODE_CLASS_MAPPINGS,
    **COMPARISON_NODE_CLASS_MAPPINGS,
    **IMAGE_NODE_CLASS_MAPPINGS,
    **SAVE_NODE_CLASS_MAPPINGS,
    "H3StudioLoader": H3StudioOptimizedLoader,
    "H3StudioContextSamplingPreset": H3StudioStableContextSamplingPreset,
    "H3StudioDecode": H3StudioStableDecode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3StudioLoader": "H3 Studio · Model Loader",
    "H3StudioDirector": "H3 Studio · Image Director",
    "H3StudioCondition": "H3 Studio · Condition & Route",
    "H3StudioOutput": "H3 Studio · Unpack Generation",
    "H3StudioContextInspector": "H3 Studio · Context Inspector",
    "H3StudioContextSamplingPreset": "H3 Studio · Director Sampling Preset",
    "H3StudioTAEH3Preview": "H3 Studio · Live Preview (TAEH3)",
    **BENCHMARK_NODE_DISPLAY_NAME_MAPPINGS,
    **COMPARISON_NODE_DISPLAY_NAME_MAPPINGS,
    **IMAGE_NODE_DISPLAY_NAME_MAPPINGS,
    **SAVE_NODE_DISPLAY_NAME_MAPPINGS,
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
