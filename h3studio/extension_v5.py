"""ComfyUI registration surface for H3 Studio max-speed adaptive runtime v5."""

from __future__ import annotations

from .nodes.benchmark import NODE_CLASS_MAPPINGS as BENCHMARK_NODE_CLASS_MAPPINGS
from .nodes.benchmark import NODE_DISPLAY_NAME_MAPPINGS as BENCHMARK_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.comparison import NODE_CLASS_MAPPINGS as COMPARISON_NODE_CLASS_MAPPINGS
from .nodes.comparison import NODE_DISPLAY_NAME_MAPPINGS as COMPARISON_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.director import H3StudioCondition, H3StudioContextInspector, H3StudioDirector, H3StudioOutput
from .nodes.image_runtime import NODE_CLASS_MAPPINGS as IMAGE_NODE_CLASS_MAPPINGS
from .nodes.image_runtime import NODE_DISPLAY_NAME_MAPPINGS as IMAGE_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.save import NODE_CLASS_MAPPINGS as SAVE_NODE_CLASS_MAPPINGS
from .nodes.save import NODE_DISPLAY_NAME_MAPPINGS as SAVE_NODE_DISPLAY_NAME_MAPPINGS
from .preview_runtime_v5 import H3StudioTAEH3PreviewV5
from .runtime_guards import install_runtime_guards
from .runtime_v5 import (
    H3StudioMaxSpeedDecode,
    H3StudioMaxSpeedLoader,
    H3StudioMaxSpeedSamplingPreset,
    install_max_speed_runtime,
    start_component_prewarm,
)
from .web_routes import register_routes

# Install model-loader/cache/conditioning policy before graph execution. Unlike
# v3 this does not hard-disable ComfyUI fast-disk on low-RAM systems.
install_max_speed_runtime()
install_runtime_guards()
register_routes()
start_component_prewarm()

NODE_CLASS_MAPPINGS = {
    "H3StudioDirector": H3StudioDirector,
    "H3StudioCondition": H3StudioCondition,
    "H3StudioOutput": H3StudioOutput,
    "H3StudioContextInspector": H3StudioContextInspector,
    "H3StudioTAEH3Preview": H3StudioTAEH3PreviewV5,
    **BENCHMARK_NODE_CLASS_MAPPINGS,
    **COMPARISON_NODE_CLASS_MAPPINGS,
    **IMAGE_NODE_CLASS_MAPPINGS,
    **SAVE_NODE_CLASS_MAPPINGS,
    "H3StudioLoader": H3StudioMaxSpeedLoader,
    "H3StudioContextSamplingPreset": H3StudioMaxSpeedSamplingPreset,
    "H3StudioDecode": H3StudioMaxSpeedDecode,
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
