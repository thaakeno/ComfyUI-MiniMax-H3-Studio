"""Typed values passed between Studio nodes inside a ComfyUI graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import CONTEXT_SCHEMA_VERSION
from .prompting.compiler import CompileResult
from .resolution import ResolutionPlan
from .routing import RouteDecision
from .state import StudioState


@dataclass(frozen=True, slots=True)
class H3StudioContext:
    schema_version: int
    state: StudioState
    compile_result: CompileResult
    resolution: ResolutionPlan
    route: RouteDecision
    images: tuple[Any, ...]
    image_filenames: tuple[str, ...]

    @classmethod
    def create(
        cls,
        state: StudioState,
        compile_result: CompileResult,
        resolution: ResolutionPlan,
        route: RouteDecision,
        images: tuple[Any, ...],
        image_filenames: tuple[str, ...],
    ) -> H3StudioContext:
        return cls(CONTEXT_SCHEMA_VERSION, state, compile_result, resolution, route, images, image_filenames)

    @property
    def prompt(self) -> str:
        return self.compile_result.native_prompt

    @property
    def width(self) -> int:
        return self.resolution.width

    @property
    def height(self) -> int:
        return self.resolution.height

    @property
    def seed(self) -> int:
        return self.state.generation.seed

    def summary(self) -> str:
        return (
            f"H3 Studio context v{self.schema_version}\n"
            f"Mode: {self.compile_result.resolved_mode}\n"
            f"Route: {self.route.summary()}\n"
            f"Canvas: {self.resolution.summary()}\n"
            f"References: {len(self.images)}\n"
            f"Seed: {self.seed}\n"
            f"Sampling: {self.state.generation.sampling_profile}\n"
            f"Diagnostics:\n{self.compile_result.diagnostics_text()}"
        )


@dataclass(frozen=True, slots=True)
class H3StudioGeneration:
    model: Any
    conditioning: Any
    latent: Any
    video_vae: Any
    requested_frames: int
    context: H3StudioContext
    fitted_source: Any
    run_info: str
