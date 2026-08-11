"""Typed values passed between Studio nodes inside a ComfyUI graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import CONTEXT_SCHEMA_VERSION, ENHANCE_COMPILE, MODE_REFERENCE_EDIT
from .prompting.compiler import CompileResult, _single_prompt, normalize_user_prompt
from .references import compile_mentions
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
        # Compile-only keeps the full four-section production brief available
        # for inspection, but the 32B H3 text encoder should not pay to encode
        # duplicated user text and generic report boilerplate on every edit.
        if self.state.prompt_options.enhance_mode == ENHANCE_COMPILE:
            prompt = normalize_user_prompt(self.state.prompt)
            compact = _single_prompt(prompt, self.compile_result.references, self.compile_result.resolved_mode)
            return compile_mentions(
                compact,
                self.compile_result.references,
                tag="subject" if self.compile_result.resolved_mode == MODE_REFERENCE_EDIT else "picture",
            )
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
