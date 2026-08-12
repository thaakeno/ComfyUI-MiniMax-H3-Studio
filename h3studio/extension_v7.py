"""ComfyUI registration surface for H3 Studio final native max-speed runtime v7."""

from __future__ import annotations

from .nodes import benchmark as benchmark_module
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
from .runtime_trace import emit
from .runtime_v5_bundle_trace import install_bundle_route_trace
from .runtime_v7 import (
    H3StudioNativeDecodeV7,
    H3StudioNativeLoaderV7,
    H3StudioNativeSamplingPresetV7,
    install_native_max_speed_runtime_v7,
)
from .runtime_v7_conditioning import install_conditioning_residency_policy_v7
from .web_routes import register_routes

# v7 performs no startup model construction, no model prewarm and no component
# monkeypatch cache. It also never rewrites ComfyUI's fast_disk flag.
install_native_max_speed_runtime_v7()
install_conditioning_residency_policy_v7()
install_bundle_route_trace()
install_runtime_guards()
register_routes()

# Benchmark Lab directly references these classes, so point it at the same
# production runtime rather than allowing a second lifecycle implementation.
benchmark_module.H3StudioContextSamplingPreset = H3StudioNativeSamplingPresetV7
benchmark_module.H3StudioDecode = H3StudioNativeDecodeV7

emit(
    "v7.extension.ready",
    memory=True,
    runtime="v7",
    startup_model_io=False,
    startup_prewarm=False,
    component_monkeypatch_cache=False,
    fast_disk_mutated_by_studio=False,
)

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
    "H3StudioLoader": H3StudioNativeLoaderV7,
    "H3StudioContextSamplingPreset": H3StudioNativeSamplingPresetV7,
    "H3StudioDecode": H3StudioNativeDecodeV7,
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
