"""ComfyUI registration surface."""

from __future__ import annotations

from .conditioning_node import install_conditioning_pipeline
from .constants import DEFAULT_MEGAPIXELS, MAX_MEGAPIXELS, MIN_MEGAPIXELS
from .nodes.benchmark import NODE_CLASS_MAPPINGS as BENCHMARK_NODE_CLASS_MAPPINGS
from .nodes.benchmark import NODE_DISPLAY_NAME_MAPPINGS as BENCHMARK_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.director import (
    H3StudioCondition,
    H3StudioContextInspector,
    H3StudioContextSamplingPreset,
    H3StudioDirector,
    H3StudioOutput,
)
from .nodes.image_runtime import NODE_CLASS_MAPPINGS as IMAGE_NODE_CLASS_MAPPINGS
from .nodes.image_runtime import NODE_DISPLAY_NAME_MAPPINGS as IMAGE_NODE_DISPLAY_NAME_MAPPINGS
from .nodes.loader import H3StudioLoader
from .nodes.preview import H3StudioTAEH3Preview
from .web_routes import register_routes

# Benchmark code imports the canonical H3StudioCondition class directly before
# registration. Install once on that shared class object so every caller uses
# the same staged cache / DynamicVRAM handoff implementation.
install_conditioning_pipeline(H3StudioCondition)
register_routes()


class H3StudioDirectResolutionDirector(H3StudioDirector):
    """Director registration with the corrected direct-resolution input range.

    The implementation stays in ``H3StudioDirector``; this small registration
    shim prevents ComfyUI's server-side input validation from rejecting values
    above the legacy 2 MP ceiling while Issue #1 is being verified.
    """

    @classmethod
    def INPUT_TYPES(cls):
        inputs = super().INPUT_TYPES()
        inputs["required"]["megapixels"] = (
            "FLOAT",
            {
                "default": DEFAULT_MEGAPIXELS,
                "min": MIN_MEGAPIXELS,
                "max": MAX_MEGAPIXELS,
                "step": 0.05,
            },
        )
        return inputs


NODE_CLASS_MAPPINGS = {
    "H3StudioLoader": H3StudioLoader,
    "H3StudioDirector": H3StudioDirectResolutionDirector,
    "H3StudioCondition": H3StudioCondition,
    "H3StudioOutput": H3StudioOutput,
    "H3StudioContextInspector": H3StudioContextInspector,
    "H3StudioContextSamplingPreset": H3StudioContextSamplingPreset,
    "H3StudioTAEH3Preview": H3StudioTAEH3Preview,
    **BENCHMARK_NODE_CLASS_MAPPINGS,
    **IMAGE_NODE_CLASS_MAPPINGS,
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
    **IMAGE_NODE_DISPLAY_NAME_MAPPINGS,
}
