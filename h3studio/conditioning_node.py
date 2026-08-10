"""Optimized implementation for the canonical H3 Studio Condition node."""

from __future__ import annotations

from typing import Any

from .conditioning_cache import release_dynamic_device_residency, run_conditioning_pipeline


def condition_with_staged_cache(self, h3_bundle: Any, studio_context: Any):
    """Condition H3 with independent caches and an explicit DynamicVRAM handoff."""

    # Imports stay local so pure-unit tests can import the cache helpers without
    # requiring a running ComfyUI installation.
    from .context import H3StudioContext, H3StudioGeneration
    from .nodes.director import FRAME_PROFILE_TO_RUNTIME
    from .nodes.loader import H3StudioBundle

    if not isinstance(h3_bundle, H3StudioBundle):
        raise ValueError("Connect H3 Studio Loader's h3_bundle output.")
    if not isinstance(studio_context, H3StudioContext):
        raise ValueError("Connect H3 Studio Director's studio_context output.")

    route = studio_context.route.selected
    images = tuple(studio_context.images)
    runtime_mode = "text_to_image (FL2VA)"
    used_images = images
    route_note = ""
    if route == "ref2va" and images:
        runtime_mode = "reference_edit (REF2VA)"
    elif route == "fl2va" and images:
        runtime_mode = "image_to_image (FL2VA)"
        if len(images) > 1:
            used_images = images[:1]
            route_note = " Forced FL2VA uses only Image 1 as the first-frame anchor."
    elif route == "ref2va" and not images:
        runtime_mode = "text_to_image (FL2VA)"
        route_note = " Experimental REF2VA-without-images model route uses text-only conditioning."

    frame_preset = FRAME_PROFILE_TO_RUNTIME[studio_context.state.generation.frame_profile]
    stages = run_conditioning_pipeline(
        h3_bundle,
        studio_context,
        route=route,
        runtime_mode=runtime_mode,
        used_images=used_images,
        frame_preset=frame_preset,
        source_fit="crop_center",
        reference_size="max_identity_2048",
    )

    # Reference/source VAE work is finished at this point. Give those dynamic
    # device pages back before the H3 transformer is requested for sampling.
    vae_release = release_dynamic_device_residency(h3_bundle.video_vae, "video_vae")
    model = h3_bundle.model_for(route)
    final_vae = (
        h3_bundle.image_vae_for_decode()
        if studio_context.state.generation.frame_profile == "image_vae_1"
        else h3_bundle.video_vae
    )
    runtime_info = (
        f"{stages.runtime_info} Conditioning stages: {stages.diagnostics} | "
        f"pre_sampler_residency={vae_release.summary}."
    )
    run_info = f"{studio_context.summary()}\n\nRuntime: {runtime_info}{route_note}"
    generation = H3StudioGeneration(
        model=model,
        conditioning=stages.conditioning,
        latent=stages.latent,
        video_vae=final_vae,
        requested_frames=stages.requested_frames,
        context=studio_context,
        fitted_source=stages.fitted_source,
        run_info=run_info,
    )
    return (
        model,
        generation,
        stages.conditioning,
        stages.latent,
        final_vae,
        stages.requested_frames,
        run_info,
    )


def install_conditioning_pipeline(condition_cls: type) -> None:
    """Install the implementation on the canonical class object.

    `nodes.benchmark` imports H3StudioCondition directly before extension
    registration. Patching the canonical class once at extension startup keeps
    normal generation and benchmark/in-process callers on exactly the same
    optimized path instead of maintaining two subtly different Condition nodes.
    """

    condition_cls.condition = condition_with_staged_cache
    condition_cls.DESCRIPTION = (
        "Apply FL2VA/REF2VA with staged prompt/reference/latent caching and an explicit DynamicVRAM residency handoff."
    )
