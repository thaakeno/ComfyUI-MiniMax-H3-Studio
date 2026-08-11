"""Dependency-free lazy output selection for the maintained workflow."""

from __future__ import annotations


class H3StudioLazyImageSwitch:
    """Request only the normal image or benchmark image branch from ComfyUI."""

    CATEGORY = "H3 Studio/Benchmark"
    FUNCTION = "select"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "selected_mode")
    DESCRIPTION = (
        "Official lazy-evaluation switch: benchmark ON never evaluates the normal sampler branch, "
        "and OFF never evaluates the matrix."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "benchmark_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "OFF runs one normal image. ON runs only the selected A/B matrix—never an extra seventh image.",
                    },
                ),
            },
            "optional": {
                "normal_image": ("IMAGE", {"lazy": True}),
                "benchmark_image": ("IMAGE", {"lazy": True}),
            },
        }

    def check_lazy_status(self, benchmark_enabled: bool, normal_image=None, benchmark_image=None):
        selected = "benchmark_image" if benchmark_enabled else "normal_image"
        return [selected] if locals()[selected] is None else []

    @staticmethod
    def select(benchmark_enabled: bool, normal_image=None, benchmark_image=None):
        if benchmark_enabled:
            if benchmark_image is None:
                raise ValueError("Benchmark image branch was not connected.")
            return benchmark_image, "A/B benchmark"
        if normal_image is None:
            raise ValueError("Normal image branch was not connected.")
        return normal_image, "Normal generation"
