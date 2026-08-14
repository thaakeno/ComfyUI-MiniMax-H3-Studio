"""ComfyUI registration surface."""

from __future__ import annotations

from .dependency_web import register_dependency_routes
from .nodes.benchmark import NODE_CLASS_MAPPINGS as BENCHMARK_NODE_CLASS_MAPPINGS
from .nodes.benchmark import NODE_DISPLAY_NAME_MAPPINGS as BENCHMARK_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.comparison import NODE_CLASS_MAPPINGS as COMPARISON_NODE_CLASS_MAPPINGS
from .nodes.comparison import NODE_DISPLAY_NAME_MAPPINGS as COMPARISON_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.decode import H3StudioDecode
from .nodes.director import (
    H3StudioContextInspector,
    H3StudioDirector,
    H3StudioOutput,
)
from .nodes.image_runtime import NODE_CLASS_MAPPINGS as IMAGE_NODE_CLASS_MAPPINGS
from .nodes.image_runtime import NODE_DISPLAY_NAME_MAPPINGS as IMAGE_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.loader import H3StudioLoader
from .nodes.model_setup import H3StudioModelSetup
from .nodes.preview import H3StudioTAEH3Preview
from .nodes.runtime import H3StudioRuntimeCondition, H3StudioRuntimeSamplingPreset
from .nodes.save import NODE_CLASS_MAPPINGS as SAVE_NODE_CLASS_MAPPINGS
from .nodes.save import NODE_DISPLAY_NAME_MAPPINGS as SAVE_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.smart_benchmark import NODE_CLASS_MAPPINGS as SMART_BENCHMARK_NODE_CLASS_MAPPINGS
from .nodes.smart_benchmark import NODE_DISPLAY_NAME_MAPPINGS as SMART_BENCHMARK_NODE_DISPLAY_NAME_MAPPINGS
from .runtime_guards import install_runtime_guards
from .runtime_web import register_runtime_routes
from .web_routes import register_routes

install_runtime_guards()
register_routes()
register_runtime_routes()
register_dependency_routes()

NODE_CLASS_MAPPINGS = {
    "H3StudioLoader": H3StudioLoader,
    "H3StudioDirector": H3StudioDirector,
    "H3StudioCondition": H3StudioRuntimeCondition,
    "H3StudioOutput": H3StudioOutput,
    "H3StudioContextInspector": H3StudioContextInspector,
    "H3StudioContextSamplingPreset": H3StudioRuntimeSamplingPreset,
    "H3StudioTAEH3Preview": H3StudioTAEH3Preview,
    "H3StudioModelSetup": H3StudioModelSetup,
    **BENCHMARK_NODE_CLASS_MAPPINGS,
    **SMART_BENCHMARK_NODE_CLASS_MAPPINGS,
    **COMPARISON_NODE_CLASS_MAPPINGS,
    **IMAGE_NODE_CLASS_MAPPINGS,
    "H3StudioDecode": H3StudioDecode,
    **SAVE_NODE_CLASS_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3StudioLoader": "H3 Studio · Model Loader",
    "H3StudioDirector": "H3 Studio · Image Director",
    "H3StudioCondition": "H3 Studio · Condition & Route",
    "H3StudioOutput": "H3 Studio · Unpack Generation",
    "H3StudioContextInspector": "H3 Studio · Context Inspector",
    "H3StudioContextSamplingPreset": "H3 Studio · Director Sampling Preset",
    "H3StudioTAEH3Preview": "H3 Studio · Live Preview (TAEH3)",
    "H3StudioModelSetup": "H3 Studio · Model Setup",
    **BENCHMARK_NODE_DISPLAY_NAME_MAPPINGS,
    **SMART_BENCHMARK_NODE_DISPLAY_NAME_MAPPINGS,
    **COMPARISON_NODE_DISPLAY_NAME_MAPPINGS,
    **IMAGE_NODE_DISPLAY_NAME_MAPPINGS,
    "H3StudioDecode": "H3 Studio · Native H3 VAE Decode",
    **SAVE_NODE_DISPLAY_NAME_MAPPINGS,
}