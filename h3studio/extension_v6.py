"""ComfyUI registration surface for H3 Studio native-first max-speed runtime v6."""

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
from .runtime_v6 import (
    H3StudioNativeDecode,
    H3StudioNativeLoader,
    H3StudioNativeSamplingPreset,
    install_native_max_speed_runtime,
)
from .runtime_v6_conditioning import install_conditioning_residency_policy
from .web_routes import register_routes

# Important: v6 performs no startup model construction and starts no background
# model-loading thread. Loader/CLIP/VAE/transformer construction begins only when
# the graph actually executes.
install_native_max_speed_runtime()
install_conditioning_residency_policy()
install_bundle_route_trace()
install_runtime_guards()
register_routes()

benchmark_module.H3StudioContextSamplingPreset = H3StudioNativeSamplingPreset
benchmark_module.H3StudioDecode = H3StudioNativeDecode

emit(
    "v6.extension.ready",
    memory=True,
    runtime="v6",
    startup_model_io=False,
    startup_prewarm=False,
    component_monkeypatch_cache=False,
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
    "H3StudioLoader": H3StudioNativeLoader,
    "H3StudioContextSamplingPreset": H3StudioNativeSamplingPreset,
    "H3StudioDecode": H3StudioNativeDecode,
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
