"""Primary Studio controller, conditioning bridge and context utilities."""

from __future__ import annotations

import logging
import threading
from dataclasses import replace
from typing import Any

from ..conditioning_cache import run_conditioning_pipeline
from ..console_report import format_execution_report
from ..constants import (
    ASPECT_RATIOS,
    ENHANCE_COMPILE,
    ENHANCE_MODES,
    MAX_MEGAPIXELS,
    MAX_REFERENCE_IMAGES,
    MODE_AUTO,
    MODE_REFERENCE_EDIT,
    MODES,
    REFERENCE_ROLES,
    ROUTES,
    SAMPLING_PROFILES,
)
from ..context import H3StudioContext, H3StudioGeneration
from ..image_inputs import collect_images, image_metadata
from ..prompting.compiler import PromptCompiler
from ..prompting.vlm import compile_with_optional_vlm
from ..references import ReferenceImage, stable_reference_id
from ..routing import choose_route, validate_generation_contract
from ..state import StudioState
from .loader import H3StudioBundle

LOGGER = logging.getLogger(__name__)

_PDD_PATCH_CACHE_LOCK = threading.RLock()
_PDD_PATCH_CACHE_KEY = None
_PDD_PATCH_CACHE_VALUE = None
_LIGHTX_PATCH_CACHE_LOCK = threading.RLock()
_LIGHTX_PATCH_CACHE_KEY = None
_LIGHTX_PATCH_CACHE_VALUE = None

LEGACY_MODE_IMAGE = "image"
LEGACY_MODE_REFERENCE = "reference"
LEGACY_RESOLUTIONS = ("480P", "768P", "1024P", "Custom")
LEGACY_REF_SIZES = ("1k", "2k")
FRAME_PROFILE_TO_RUNTIME = {
    "image_vae_1": "experimental image VAE | 1 frame",
    "recommended_5": "recommended | 5 frames",
    "balanced_9": "extended quality | 9 frames",
    "quality_13": "high quality | 13 frames",
    "maximum_20": "maximum quality | 20 frames (slow)",
}
SAMPLING_PROFILE_TO_RUNTIME = {
    "base_quality_20": "base quality | RES 20 steps",
    "base_balanced_12": "base speed | RES 12 steps",
    "lightx_er_sde_4": "LightX v0.1 | ER-SDE 4 steps",
    "lightx_sa_solver_4": "LightX v0.1 | SA-Solver 4 steps",
}
SAMPLING_PROFILE_ALIASES = {
    "turbo_er_sde_6": "lightx_er_sde_4",
    "turbo_sa_solver_4": "lightx_sa_solver_4",
}


def _frame_profile(value: str) -> str:
    value = str(value or "recommended_5")
    return value if value in FRAME_PROFILE_TO_RUNTIME else "recommended_5"


def _sampling_profile(value: str) -> str:
    value = str(value or "base_quality_20")
    value = SAMPLING_PROFILE_ALIASES.get(value, value)
    return value if value in SAMPLING_PROFILES else "base_quality_20"


def _state_from_widgets(
    prompt: str,
    mode: str,
    aspect_ratio: str,
    width: int,
    height: int,
    megapixels: float,
    seed: int,
    enhance_mode: str,
    adherence: float,
    route: str,
    sampling_profile: str,
    frame_profile: str,
    analyzer_model: str,
    studio_state: str,
    images: tuple[Any, ...],
    filenames: tuple[str, ...],
    storage_names: tuple[str | None, ...],
    kwargs: dict[str, Any],
) -> StudioState:
    try:
        persisted = StudioState.from_json(studio_state) if str(studio_state or "").strip() else StudioState()
    except Exception as exc:
        raise ValueError(
            "H3 Studio could not restore its saved state. Reload the workflow and use the preserved recovery value."
        ) from exc
    references = []
    existing_by_ordinal = {reference.ordinal: reference for reference in persisted.references}
    for ordinal, filename in enumerate(filenames, start=1):
        existing = existing_by_ordinal.get(ordinal)
        storage_name = storage_names[ordinal - 1] if ordinal <= len(storage_names) else None
        width, height, fingerprint = image_metadata(images[ordinal - 1])
        role = str(kwargs.get(f"role_{ordinal}") or (existing.role if existing else "auto"))
        retention = str(
            kwargs.get(f"retention_{ordinal}") or (existing.retention if existing else "attribute_transfer")
        )
        description = str(kwargs.get(f"description_{ordinal}") or (existing.description if existing else ""))
        content_changed = bool(existing and existing.fingerprint and existing.fingerprint != fingerprint)
        if content_changed and existing.description_auto:
            description = ""
        if content_changed and "role_origin:vision" in existing.tags:
            role = "auto"
        tags = existing.tags if existing else ()
        if content_changed:
            tags = tuple(
                tag
                for tag in tags
                if tag != "visually_analyzed" and not tag.startswith(("role_origin:", "retention_origin:"))
            )
        references.append(
            ReferenceImage(
                id=existing.id if existing else stable_reference_id(filename, ordinal),
                filename=filename,
                ordinal=ordinal,
                storage_name=storage_name or (existing.storage_name if existing and existing.filename == filename else None),
                role=role if role in REFERENCE_ROLES else "auto",
                retention=retention,
                description=description,
                enabled=existing.enabled if existing else True,
                source_node_id=existing.source_node_id if existing else None,
                source_slot=existing.source_slot if existing else 0,
                width=width,
                height=height,
                fingerprint=fingerprint,
                thumbnail=existing.thumbnail if existing else None,
                tags=tags,
                role_auto=existing.role_auto if existing else role == "auto",
                retention_auto=existing.retention_auto if existing else role == "auto",
                description_auto=existing.description_auto if existing else not description.strip(),
            )
        )
    if str(studio_state or "").strip() and persisted.generation.mode in MODES:
        resolved_mode = persisted.generation.mode
    else:
        resolved_mode = MODE_REFERENCE_EDIT if str(mode) == LEGACY_MODE_REFERENCE else MODE_AUTO
    legacy_vlm = enhance_mode == "vlm"
    resolved_enhance_mode = ENHANCE_COMPILE if legacy_vlm else enhance_mode
    prompt_options = replace(
        persisted.prompt_options,
        enhance_mode=resolved_enhance_mode if resolved_enhance_mode in ENHANCE_MODES else ENHANCE_COMPILE,
        analyze_images=persisted.prompt_options.analyze_images or legacy_vlm,
        adherence=max(0.0, min(1.0, float(adherence))),
        analyzer_model=str(analyzer_model or persisted.prompt_options.analyzer_model),
    )
    generation = replace(
        persisted.generation,
        mode=resolved_mode,
        route=route if route in ROUTES else "auto",
        seed=max(0, int(seed)),
        aspect_ratio=str(aspect_ratio or "1:1"),
        megapixels=float(megapixels),
        custom_width=int(width),
        custom_height=int(height),
        sampling_profile=_sampling_profile(sampling_profile),
        frame_profile=_frame_profile(frame_profile),
    )
    return StudioState(
        prompt=str(prompt or persisted.prompt),
        references=tuple(references),
        prompt_options=prompt_options,
        generation=generation,
        ui=persisted.ui,
        diagnostics=persisted.diagnostics,
    )


class H3StudioDirector:
    """Visible image-direction node with Easy-compatible virtual media links."""

    CATEGORY = "H3 Studio"
    FUNCTION = "direct"
    RETURN_TYPES = ("H3_STUDIO_CONTEXT", "STRING", "STRING", "INT", "INT", "INT", "STRING")
    RETURN_NAMES = ("studio_context", "compiled_prompt", "state_json", "width", "height", "seed", "diagnostics")
    DESCRIPTION = (
        "Compose an H3 still-image request, organize up to nine ordered images and compile friendly @Image references "
        "into H3-native reference conditioning instructions."
    )

    @classmethod
    def INPUT_TYPES(cls):
        optional: dict[str, Any] = {
            "media": ("*",),
            "media_filename": ("STRING", {"default": ""}),
            "h3_bundle": ("H3_STUDIO_BUNDLE",),
        }
        for index in range(1, MAX_REFERENCE_IMAGES + 1):
            optional[f"media_{index}"] = ("*",)
            optional[f"media_type_{index}"] = ("STRING", {"default": "image"})
            optional[f"media_filename_{index}"] = ("STRING", {"default": ""})
            optional[f"role_{index}"] = (list(REFERENCE_ROLES), {"default": "auto"})
            optional[f"retention_{index}"] = (
                ["attribute_transfer", "fully_preserved", "partially_preserved", "reference_only"],
                {"default": "attribute_transfer"},
            )
            optional[f"description_{index}"] = ("STRING", {"default": "", "multiline": True})
        return {
            "required": {
                # First twelve widgets intentionally retain Easy's order. The
                # adapted mention editor can safely migrate existing workflows.
                "mode": ([LEGACY_MODE_IMAGE, LEGACY_MODE_REFERENCE], {"default": LEGACY_MODE_IMAGE}),
                "prompt": ("STRING", {"multiline": True, "dynamicPrompts": True, "default": ""}),
                "resolution": (list(LEGACY_RESOLUTIONS), {"default": "Custom"}),
                "aspect_ratio": (list(ASPECT_RATIOS.keys()), {"default": "1:1"}),
                "width": ("INT", {"default": 1024, "min": 32, "max": 16384, "step": 32}),
                "height": ("INT", {"default": 1024, "min": 32, "max": 16384, "step": 32}),
                "seconds": ("FLOAT", {"default": 5.0, "min": 5.0, "max": 5.0, "step": 1.0}),
                "advanced": ("BOOLEAN", {"default": False}),
                "fps": ("FLOAT", {"default": 24.0, "min": 24.0, "max": 24.0, "step": 1.0}),
                "keyframe_role": (["first", "last"], {"default": "first"}),
                "ref_image_size": (list(LEGACY_REF_SIZES), {"default": "2k"}),
                "reference_mention_mode": (["index", "filename"], {"default": "index"}),
                # Image Studio controls.
                "megapixels": ("FLOAT", {"default": 1.0, "min": 0.20, "max": MAX_MEGAPIXELS, "step": 0.05}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2**63 - 1, "control_after_generate": True}),
                "enhance_mode": (list(ENHANCE_MODES), {"default": ENHANCE_COMPILE}),
                "adherence": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 1.0, "step": 0.05}),
                "route": (list(ROUTES), {"default": "auto"}),
                "sampling_profile": (list(SAMPLING_PROFILES.keys()), {"default": "base_quality_20"}),
                "frame_profile": (list(FRAME_PROFILE_TO_RUNTIME.keys()), {"default": "recommended_5"}),
                "analyzer_model": ("STRING", {"default": ""}),
                "studio_state": ("STRING", {"default": "", "multiline": True}),
            },
            "optional": optional,
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Preserve seed control and media-link changes; Comfy handles unchanged
        # upstream image tensors through its normal cache.
        return "|".join(
            str(kwargs.get(key, ""))
            for key in (
                "prompt",
                "mode",
                "aspect_ratio",
                "megapixels",
                "seed",
                "route",
                "sampling_profile",
                "studio_state",
            )
        )

    @classmethod
    def direct(
        cls,
        mode,
        prompt,
        resolution,
        aspect_ratio,
        width,
        height,
        seconds,
        advanced,
        fps,
        keyframe_role,
        ref_image_size,
        reference_mention_mode,
        megapixels,
        seed,
        enhance_mode,
        adherence,
        route,
        sampling_profile,
        frame_profile,
        analyzer_model,
        studio_state,
        **kwargs,
    ):
        del resolution, seconds, advanced, fps, keyframe_role, ref_image_size, reference_mention_mode
        h3_bundle = kwargs.pop("h3_bundle", None)
        images, filenames, storage_names = collect_images(kwargs)
        state = _state_from_widgets(
            prompt,
            mode,
            aspect_ratio,
            width,
            height,
            megapixels,
            seed,
            enhance_mode,
            adherence,
            route,
            sampling_profile,
            frame_profile,
            analyzer_model,
            studio_state,
            images,
            filenames,
            storage_names,
            kwargs,
        )
        validate_generation_contract(
            state.generation.mode,
            state.generation.route,
            state.generation.sampling_profile,
            state.reference_count,
        )
        compiler = PromptCompiler()
        enhanced_prompt = state.prompt
        if state.prompt_options.analyze_images and images:
            from ..prompting.comfy_analyzer import analyze_references

            analyzer_bundle = h3_bundle if isinstance(h3_bundle, H3StudioBundle) else None
            analyzer = analyzer_bundle.analyzer_clip if analyzer_bundle else None
            analyzed_references, enhanced_prompt, vlm_note = analyze_references(
                analyzer,
                state.prompt,
                state.enabled_references,
                images,
                analyzer_name=analyzer_bundle.analyzer_name or "" if analyzer_bundle else "",
                clip_loader=analyzer_bundle.analyzer_for_analysis if analyzer_bundle else None,
                max_image_edge=state.prompt_options.analyzer_resolution,
                deep_enhancement=state.prompt_options.deep_enhancement,
                writer_clip=analyzer_bundle.prompt_writer_clip if analyzer_bundle else None,
                writer_name=analyzer_bundle.prompt_writer_name or "" if analyzer_bundle else "",
                writer_loader=analyzer_bundle.writer_for_enhancement if analyzer_bundle else None,
            )
            state = state.with_references(analyzed_references)
            compile_result = compiler.compile(state.with_prompt(enhanced_prompt))
        else:
            compile_result, vlm_note = compile_with_optional_vlm(state, images, compiler=compiler)
        # Persist both deterministic and visual role decisions into the cards.
        state = state.with_references(compile_result.references)
        plan = state.generation.resolution()
        from ..acceleration import route_for_profile

        route_request = route_for_profile(
            state.generation.sampling_profile,
            state.generation.route,
            len(images),
        )
        route_decision = choose_route(route_request, compile_result.resolved_mode, len(images))
        if route_request == "ref2va" and state.generation.route == "auto":
            route_decision = replace(
                route_decision,
                reason="selected REF2VA because the active Mamad8 PDD profile is trained for reference generation",
            )
        context = H3StudioContext.create(state, compile_result, plan, route_decision, images, filenames)
        LOGGER.info("\n%s", format_execution_report(context, vlm_note))
        diagnostics = context.summary() + vlm_note
        reference_labels = [
            f"@Image{reference.ordinal} · {reference.effective_role} · {reference.retention} · {reference.filename}"
            for reference in compile_result.references
        ]
        result = (
            context,
            compile_result.native_prompt,
            state.to_json(),
            plan.width,
            plan.height,
            state.generation.seed,
            diagnostics,
        )
        return {
            "ui": {
                "compiled_prompt": [compile_result.native_prompt],
                "enhanced_instruction": [enhanced_prompt],
                "reference_labels": reference_labels,
                "reference_roles": [reference.effective_role for reference in compile_result.references],
                "reference_retentions": [reference.retention for reference in compile_result.references],
                "reference_descriptions": [reference.description for reference in compile_result.references],
                "diagnostics": [diagnostics],
            },
            "result": result,
        }


class H3StudioCondition:
    """Bridge Studio direction into native H3 conditioning and latent values."""

    CATEGORY = "H3 Studio"
    FUNCTION = "condition"
    RETURN_TYPES = ("MODEL", "H3_STUDIO_GENERATION", "CONDITIONING", "LATENT", "VAE", "INT", "STRING")
    RETURN_NAMES = ("model", "generation", "positive", "h3_latent", "video_vae", "requested_frames", "run_info")
    DESCRIPTION = (
        "Apply FL2VA/REF2VA with independent prompt, reference-VAE, source-VAE and latent caches. "
        "ComfyUI alone owns model residency and offloading."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "h3_bundle": ("H3_STUDIO_BUNDLE",),
                "studio_context": ("H3_STUDIO_CONTEXT",),
            }
        }

    def condition(self, h3_bundle, studio_context):
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
        model = h3_bundle.model_for(route)
        run_info = (
            f"{studio_context.summary()}\n\nRuntime: {stages.runtime_info} "
            f"Conditioning stages: {stages.diagnostics}.{route_note}"
        )
        final_vae = (
            h3_bundle.image_vae_for_decode()
            if studio_context.state.generation.frame_profile == "image_vae_1"
            else h3_bundle.video_vae
        )
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


class H3StudioOutput:
    CATEGORY = "H3 Studio"
    FUNCTION = "unpack"
    RETURN_TYPES = ("CONDITIONING", "LATENT", "VAE", "INT", "IMAGE", "STRING")
    RETURN_NAMES = ("positive", "h3_latent", "video_vae", "requested_frames", "fitted_source", "run_info")
    DESCRIPTION = "Unpack an H3 Studio generation bundle for custom sampling workflows."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"generation": ("H3_STUDIO_GENERATION",)}}

    @staticmethod
    def unpack(generation):
        if not isinstance(generation, H3StudioGeneration):
            raise ValueError("Connect H3 Studio Condition's generation output.")
        return (
            generation.conditioning,
            generation.latent,
            generation.video_vae,
            generation.requested_frames,
            generation.fitted_source,
            generation.run_info,
        )


class H3StudioContextSamplingPreset:
    """Resolve the sampling recipe selected in the Studio Director."""

    CATEGORY = "H3 Studio"
    FUNCTION = "build"
    RETURN_TYPES = ("MODEL", "SAMPLER", "SIGMAS", "STRING")
    RETURN_NAMES = ("model", "sampler", "sigmas", "sampling_info")
    DESCRIPTION = (
        "Apply the Director's visible Speed selection inside a workflow or subgraph. Base and LightX recipes remain "
        "local; Mamad8 PDD profiles delegate to the separately installed external node package and matching artifacts."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("MODEL",), "studio_context": ("H3_STUDIO_CONTEXT",)}}

    def build(self, model, studio_context):
        global _PDD_PATCH_CACHE_KEY, _PDD_PATCH_CACHE_VALUE
        global _LIGHTX_PATCH_CACHE_KEY, _LIGHTX_PATCH_CACHE_VALUE
        from ..acceleration import build_lightx_backend, build_pdd_backend, is_pdd_profile
        from .image_runtime import H3StudioSamplingPreset

        if not isinstance(studio_context, H3StudioContext):
            raise ValueError("Connect H3 Studio Director's studio_context output.")
        profile = _sampling_profile(studio_context.state.generation.sampling_profile)
        if is_pdd_profile(profile):
            cache_key = (id(model), profile, studio_context.route.selected)
            with _PDD_PATCH_CACHE_LOCK:
                if cache_key == _PDD_PATCH_CACHE_KEY and _PDD_PATCH_CACHE_VALUE is not None:
                    result = _PDD_PATCH_CACHE_VALUE
                    result = (*result[:3], f"{result[3]} | patch_cache=hit")
                    LOGGER.info("[H3 Studio] PDD patch cache hit; reused LoRA, heads and patched model")
                else:
                    result = build_pdd_backend(
                        model,
                        profile,
                        selected_route=studio_context.route.selected,
                        reference_count=len(studio_context.images),
                    )
                    _PDD_PATCH_CACHE_KEY = cache_key
                    _PDD_PATCH_CACHE_VALUE = result
        elif profile.startswith("lightx_"):
            cache_key = (id(model), profile)
            with _LIGHTX_PATCH_CACHE_LOCK:
                if cache_key == _LIGHTX_PATCH_CACHE_KEY and _LIGHTX_PATCH_CACHE_VALUE is not None:
                    result = _LIGHTX_PATCH_CACHE_VALUE
                    result = (*result[:3], f"{result[3]} | patch_cache=hit")
                    LOGGER.info("[H3 Studio] LightX patch cache hit; reused the loaded adapter")
                else:
                    result = build_lightx_backend(model, profile)
                    _LIGHTX_PATCH_CACHE_KEY = cache_key
                    _LIGHTX_PATCH_CACHE_VALUE = result
        else:
            runtime_profile = SAMPLING_PROFILE_TO_RUNTIME[profile]
            result = H3StudioSamplingPreset().build(model, runtime_profile)
        LOGGER.info("\n[H3 Studio] Sampling resolved\n  %s", result[3])
        return result


class H3StudioContextInspector:
    CATEGORY = "H3 Studio/Utilities"
    FUNCTION = "inspect"
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT", "INT")
    RETURN_NAMES = ("compiled_prompt", "context_info", "width", "height", "seed")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"studio_context": ("H3_STUDIO_CONTEXT",)}}

    @staticmethod
    def inspect(studio_context):
        if not isinstance(studio_context, H3StudioContext):
            raise ValueError("Connect an H3 Studio context.")
        return (
            studio_context.prompt,
            studio_context.summary(),
            studio_context.width,
            studio_context.height,
            studio_context.seed,
        )
