"""ComfyUI registration surface."""

from __future__ import annotations

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
from .nodes.preview import H3StudioTAEH3Preview
from .nodes.save import NODE_CLASS_MAPPINGS as SAVE_NODE_CLASS_MAPPINGS
from .nodes.save import NODE_DISPLAY_NAME_MAPPINGS as SAVE_NODE_DISPLAY_NAME_MAPPINGS
from .runtime_guards import install_runtime_guards
from .runtime_stability import install_runtime_stability, runtime_node_classes
from .web_routes import register_routes

install_runtime_guards()
install_runtime_stability()
register_routes()
H3StudioStableContextSamplingPreset, H3StudioStableDecode = runtime_node_classes()

NODE_CLASS_MAPPINGS = {
    "H3StudioDirector": H3StudioDirector,
    "H3StudioCondition": H3StudioCondition,
    "H3StudioOutput": H3StudioOutput,
    "H3StudioContextInspector": H3StudioContextInspector,
    "H3StudioTAEH3Preview": H3StudioTAEH3Preview,
    **BENCHMARK_NODE_CLASS_MAPPINGS,
    **COMPARISON_NODE_CLASS_MAPPINGS,
    **IMAGE_NODE_CLASS_MAPPINGS,
    **SAVE_NODE_CLASS_MAPPINGS,
    # Keep public node ids stable while applying only the performance policies
    # that survived real L4 validation.
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
