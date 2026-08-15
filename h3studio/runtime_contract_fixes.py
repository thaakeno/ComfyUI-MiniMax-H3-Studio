"""Make H3 Studio's resolved generation mode the execution contract.

The Director already resolves Auto into text_to_image, image_to_image, or
reference_edit. Conditioning must consume that resolved mode directly rather
than inferring another mode from ``route + bool(images)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import MODE_IMAGE_TO_IMAGE, MODE_REFERENCE_EDIT, MODE_TEXT_TO_IMAGE
from .context import H3StudioContext


@dataclass(frozen=True, slots=True)
class ConditioningContract:
    runtime_mode: str
    used_images: tuple[Any, ...]
    pixel_conditioning: str
    note: str = ""


def conditioning_contract(studio_context: H3StudioContext) -> ConditioningContract:
    """Translate the compiler's resolved mode into exactly one conditioning path."""

    mode = str(studio_context.compile_result.resolved_mode)
    route = str(studio_context.route.selected)
    images = tuple(studio_context.images)

    if mode == MODE_TEXT_TO_IMAGE:
        if route != "fl2va":
            raise ValueError("Text-to-image must resolve to FL2VA.")
        note = ""
        if images:
            note = (
                f" {len(images)} connected reference card(s) are metadata/prompt-analysis only; "
                "no source VAE, keyframe, or REF2VA pixel conditioning is applied."
            )
        return ConditioningContract(
            runtime_mode="text_to_image (FL2VA)",
            used_images=(),
            pixel_conditioning="none · text-only FL2VA",
            note=note,
        )

    if mode == MODE_IMAGE_TO_IMAGE:
        if route != "fl2va":
            raise ValueError("Image-to-image must resolve to FL2VA.")
        if not images:
            raise ValueError("Image-to-image requires Image 1 as its FL2VA source anchor.")
        note = ""
        if len(images) > 1:
            note = (
                f" Only Image 1 is pixel-conditioned; Images 2-{len(images)} remain reference/prompt metadata "
                "and are not inserted as FL2VA keyframes."
            )
        return ConditioningContract(
            runtime_mode="image_to_image (FL2VA)",
            used_images=images[:1],
            pixel_conditioning="@Image1 · source VAE + exact frame-0 keyframe",
            note=note,
        )

    if mode == MODE_REFERENCE_EDIT:
        if route != "ref2va":
            raise ValueError("Reference mix/edit must resolve to REF2VA.")
        if not images:
            raise ValueError("Reference mix/edit requires at least one reference image.")
        return ConditioningContract(
            runtime_mode="reference_edit (REF2VA)",
            used_images=images,
            pixel_conditioning=f"{len(images)} ordered image reference(s) · REF2VA minimax_refs",
        )

    raise ValueError(f"Unsupported resolved H3 generation mode {mode!r}.")


def install() -> None:
    """Patch the base conditioner while keeping saved workflow schemas stable."""

    from .conditioning_cache import run_conditioning_pipeline
    from .nodes.director import FRAME_PROFILE_TO_RUNTIME, H3StudioCondition
    from .nodes.loader import H3StudioBundle

    current = H3StudioCondition.condition
    if bool(getattr(current, "__h3studio_mode_contract_v2__", False)):
        return

    def condition(self, h3_bundle, studio_context):
        if not isinstance(h3_bundle, H3StudioBundle):
            raise ValueError("Connect H3 Studio Loader's h3_bundle output.")
        if not isinstance(studio_context, H3StudioContext):
            raise ValueError("Connect H3 Studio Director's studio_context output.")

        route = str(studio_context.route.selected)
        contract = conditioning_contract(studio_context)
        frame_preset = FRAME_PROFILE_TO_RUNTIME[studio_context.state.generation.frame_profile]
        stages = run_conditioning_pipeline(
            h3_bundle,
            studio_context,
            route=route,
            runtime_mode=contract.runtime_mode,
            used_images=contract.used_images,
            frame_preset=frame_preset,
            source_fit="crop_center",
            reference_size="max_identity_2048",
        )
        model = h3_bundle.model_for(route)
        requested_mode = str(studio_context.state.generation.mode)
        effective_mode = str(studio_context.compile_result.resolved_mode)
        run_info = (
            f"{studio_context.summary()}\n\n"
            f"Requested mode: {requested_mode}\n"
            f"Effective mode: {effective_mode}\n"
            f"Pixel conditioning: {contract.pixel_conditioning}\n"
            f"Runtime: {stages.runtime_info} Conditioning stages: {stages.diagnostics}.{contract.note}"
        )
        return (
            model,
            studio_context.generation,
            stages.conditioning,
            stages.latent,
            h3_bundle.video_vae,
            stages.requested_frames,
            run_info,
        )

    condition.__h3studio_mode_contract_v2__ = True
    H3StudioCondition.condition = condition


__all__ = ["ConditioningContract", "conditioning_contract", "install"]
