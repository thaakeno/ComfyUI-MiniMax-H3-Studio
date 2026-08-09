"""Primary Studio controller, conditioning bridge and context utilities."""

from __future__ import annotations

import logging
import threading
from dataclasses import replace
from typing import Any

from ..console_report import format_execution_report
from ..constants import (
    ASPECT_RATIOS,
    ENHANCE_COMPILE,
    ENHANCE_MODES,
    MAX_REFERENCE_IMAGES,
    MODE_AUTO,
    MODE_REFERENCE_EDIT,
    MODES,
    REFERENCE_ROLES,
    ROUTES,
    SAMPLING_PROFILES,
)
from ..context import H3StudioContext, H3StudioGeneration
from ..image_inputs import collect_images
from ..prompting.compiler import PromptCompiler
from ..prompting.vlm import compile_with_optional_vlm
from ..references import ReferenceImage, stable_reference_id
from ..routing import choose_route
from ..state import StudioState
from .loader import H3StudioBundle

LOGGER = logging.getLogger(__name__)

# One-entry process caches survive ComfyUI recreating a Python node instance
# between queues, while remaining bounded when the user changes model/route.
_CONDITIONING_CACHE_LOCK = threading.RLock()
_CONDITIONING_CACHE_KEY = None
_CONDITIONING_CACHE_VALUE = None
_PDD_PATCH_CACHE_LOCK = threading.RLock()
_PDD_PATCH_CACHE_KEY = None
_PDD_PATCH_CACHE_VALUE = None

LEGACY_MODE_IMAGE = "image"
LEGACY_MODE_REFERENCE = "reference"
LEGACY_RESOLUTIONS = ("480P", "768P", "1024P", "Custom")
LEGACY_REF_SIZES = ("1k", "2k")
FRAME_PROFILE_TO_RUNTIME = {
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
    except Exception:
        persisted = StudioState()
    references = []
    existing_by_ordinal = {reference.ordinal: reference for reference in persisted.references}
    for ordinal, filename in enumerate(filenames, start=1):
        existing = existing_by_ordinal.get(ordinal)
        storage_name = storage_names[ordinal - 1] if ordinal <= len(storage_names) else None
        role = str(kwargs.get(f"role_{ordinal}") or (existing.role if existing else "auto"))
        retention = str(kwargs.get(f"retention_{ordinal}") or (existing.retention if existing else "attribute_transfer"))
        description = str(kwargs.get(f"description_{ordinal}") or (existing.description if existing else ""))
        references.append(
            ReferenceImage(
                id=existing.id if existing else stable_reference_id(filename, ordinal),
                filename=filename,
                ordinal=ordinal,
                storage_name=storage_name,
                role=role if role in REFERENCE_ROLES else "auto",
                retention=retention,
                description=description,
                enabled=True,
                role_auto=existing.role_auto if existing else role == "auto",
                retention_auto=existing.retention_auto if existing else role == "auto",
            )
        )
    if str(studio_state or "").strip() and persisted.generation.mode in MODES:
        resolved_mode = persisted.generation.mode
    else:
        resolved_mode = MODE_REFERENCE_EDIT if str(mode) == LEGACY_MODE_REFERENCE else MODE_AUTO
    prompt_options = replace(
        persisted.prompt_options,
        enhance_mode=enhance_mode if enhance_mode in ENHANCE_MODES else ENHANCE_COMPILE,
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
                "megapixels": ("FLOAT", {"default": 1.0, "min": 0.20, "max": 2.0, "step": 0.05}),
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
            for key in ("prompt", "mode", "aspect_ratio", "megapixels", "seed", "route", "sampling_profile", "studio_state")
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
        compiler = PromptCompiler()
        compile_result, vlm_note = compile_with_optional_vlm(state, images, compiler=compiler)
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
            f"@Image {reference.ordinal} · {reference.effective_role} · {reference.retention} · {reference.filename}"
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
                "reference_labels": reference_labels,
                "reference_roles": [reference.effective_role for reference in compile_result.references],
                "reference_retentions": [reference.retention for reference in compile_result.references],
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
    DESCRIPTION = "Apply the selected FL2VA/REF2VA route without re-encoding the prompt twice."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "h3_bundle": ("H3_STUDIO_BUNDLE",),
                "studio_context": ("H3_STUDIO_CONTEXT",),
            }
        }

    @staticmethod
    def _image_cache_key(studio_context):
        values = []
        for index, image in enumerate(studio_context.images):
            reference = studio_context.state.references[index] if index < len(studio_context.state.references) else None
            storage_name = reference.storage_name if reference is not None else None
            if storage_name:
                values.append(("stored", storage_name, tuple(getattr(image, "shape", ()))))
                continue
            data_ptr = getattr(image, "data_ptr", None)
            pointer = data_ptr() if callable(data_ptr) else id(image)
            values.append(("tensor", pointer, getattr(image, "_version", 0), tuple(getattr(image, "shape", ()))))
        return tuple(values)

    def condition(self, h3_bundle, studio_context):
        global _CONDITIONING_CACHE_KEY, _CONDITIONING_CACHE_VALUE
        from .image_runtime import H3StudioPrepare

        if not isinstance(h3_bundle, H3StudioBundle):
            raise ValueError("Connect H3 Studio Loader's h3_bundle output.")
        if not isinstance(studio_context, H3StudioContext):
            raise ValueError("Connect H3 Studio Director's studio_context output.")
        route = studio_context.route.selected
        images = studio_context.images
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
        references = list(used_images) + [None] * (9 - len(used_images))
        cache_key = (
            h3_bundle.fl2va_name, h3_bundle.ref2va_name, h3_bundle.clip_name, h3_bundle.video_vae_name,
            route, runtime_mode, studio_context.prompt, studio_context.width, studio_context.height, frame_preset,
            self._image_cache_key(studio_context),
        )
        with _CONDITIONING_CACHE_LOCK:
            if cache_key == _CONDITIONING_CACHE_KEY and _CONDITIONING_CACHE_VALUE is not None:
                conditioning, latent, fitted, requested_frames, runtime_info = _CONDITIONING_CACHE_VALUE
                runtime_info = f"{runtime_info} Conditioning cache: HIT; Qwen3-VL/VAE reference encoding reused."
                LOGGER.info("[H3 Studio] Conditioning cache hit; skipped Qwen3-VL and reference VAE encoding")
            else:
                result = H3StudioPrepare().prepare(
                    clip=h3_bundle.clip,
                    mode=runtime_mode,
                    prompt=studio_context.prompt,
                    width=studio_context.width,
                    height=studio_context.height,
                    frame_preset=frame_preset,
                    optimize_prompt=False,
                    preserve_strength=studio_context.state.prompt_options.adherence,
                    source_fit="crop_center",
                    reference_size="max_identity_2048",
                    vae=h3_bundle.video_vae,
                    source_image=references[0],
                    reference_image_2=references[1],
                    reference_image_3=references[2],
                    reference_image_4=references[3],
                    reference_image_5=references[4],
                    reference_image_6=references[5],
                    reference_image_7=references[6],
                    reference_image_8=references[7],
                    reference_image_9=references[8],
                )
                conditioning, latent, fitted, requested_frames, _prompt, runtime_info = result
                _CONDITIONING_CACHE_KEY = cache_key
                _CONDITIONING_CACHE_VALUE = (conditioning, latent, fitted, requested_frames, runtime_info)
        model = h3_bundle.model_for(route)
        run_info = f"{studio_context.summary()}\n\nRuntime: {runtime_info}{route_note}"
        generation = H3StudioGeneration(
            model=model,
            conditioning=conditioning,
            latent=latent,
            video_vae=h3_bundle.video_vae,
            requested_frames=requested_frames,
            context=studio_context,
            fitted_source=fitted,
            run_info=run_info,
        )
        return model, generation, conditioning, latent, h3_bundle.video_vae, requested_frames, run_info


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
        from ..acceleration import build_pdd_backend, is_pdd_profile
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
        return studio_context.prompt, studio_context.summary(), studio_context.width, studio_context.height, studio_context.seed
