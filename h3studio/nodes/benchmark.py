"""One-click, same-seed MiniMax H3 resolution and acceleration comparison."""

from __future__ import annotations

import logging
import re
import time
from base64 import b64encode
from dataclasses import dataclass, replace
from io import BytesIO
from textwrap import wrap
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..benchmark import (
    SEED_STRATEGIES,
    ABVariantSpec,
    build_matrix_plan,
    short_profile_label,
)
from ..context import H3StudioContext
from .director import H3StudioCondition, H3StudioContextSamplingPreset
from .image_runtime import H3StudioDecode, H3StudioFrameSelector
from .lazy_switch import H3StudioLazyImageSwitch
from .loader import H3StudioBundle

LOGGER = logging.getLogger(__name__)
COMPARISON_KINDS = (
    "Sampling profiles x resolution",
    "VAE decode - same T=1 latent",
)
_RESOLUTION_SENTENCE = re.compile(
    r"Create one finished [^\n]+? image at approximately \d+(?:\.\d+)? megapixels "
    r"\(\d+\s*[xX×]\s*\d+\)\.",
    re.IGNORECASE,
)


@dataclass(slots=True)
class _ABResult:
    spec: ABVariantSpec
    width: int
    height: int
    actual_megapixels: float
    image: torch.Tensor | None = None
    sampling_seconds: float | None = None
    sampling_info: str = ""
    error: str = ""


def _outputs(value: Any) -> tuple[Any, ...]:
    if hasattr(value, "args"):
        return tuple(value.args)
    if isinstance(value, dict) and "result" in value:
        result = value["result"]
        return tuple(result) if isinstance(result, (tuple, list)) else (result,)
    if isinstance(value, (tuple, list)):
        return tuple(value)
    return (value,)


def _variant_context(context: H3StudioContext, spec: ABVariantSpec) -> H3StudioContext:
    generation = replace(
        context.state.generation,
        megapixels=spec.requested_megapixels,
        sampling_profile=spec.profile,
        seed=spec.seed,
    )
    state = replace(context.state, generation=generation)
    resolution = state.generation.resolution()
    replacement = (
        f"Create one finished {resolution.aspect_ratio} {resolution.orientation} image at approximately "
        f"{resolution.actual_megapixels:.2f} megapixels ({resolution.width} x {resolution.height})."
    )
    native_prompt = _RESOLUTION_SENTENCE.sub(replacement, context.compile_result.native_prompt, count=1)
    compile_result = replace(context.compile_result, native_prompt=native_prompt)
    return replace(context, state=state, resolution=resolution, compile_result=compile_result)


def _synchronize_cuda() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def _sample_one(model, conditioning, latent, video_vae, context: H3StudioContext):
    sampled, sampling_seconds, sampling_info = _sample_latent(model, conditioning, latent, context)
    image, decode_info, _decode_seconds = _decode_single(sampled, video_vae)
    del sampled
    return image, sampling_seconds, sampling_info, decode_info


def _sample_latent(model, conditioning, latent, context: H3StudioContext):
    from comfy_extras.nodes_custom_sampler import BasicGuider, RandomNoise, SamplerCustomAdvanced

    shifted_model, sampler, sigmas, sampling_info = H3StudioContextSamplingPreset().build(model, context)
    guider = _outputs(BasicGuider.get_guider(shifted_model, conditioning))[0]
    noise = _outputs(RandomNoise.get_noise(context.seed))[0]
    _synchronize_cuda()
    started = time.perf_counter()
    sampled = _outputs(SamplerCustomAdvanced.sample(noise, guider, sampler, sigmas, latent))[0]
    _synchronize_cuda()
    sampling_seconds = time.perf_counter() - started

    return sampled, sampling_seconds, sampling_info


def _decode_single(sampled, vae):
    _synchronize_cuda()
    started = time.perf_counter()
    frames, _count, decode_info, recommended_index = H3StudioDecode().decode(sampled, vae)
    selected, _debug, selected_index, _score, selection_info = H3StudioFrameSelector().select(
        frames,
        "decode_recommended",
        0,
        0,
        0.0,
        1.0,
        0.6,
        1,
        emit_candidate_batch=False,
        recommended_index=recommended_index,
    )
    image = selected[:1].detach().to(device="cpu", dtype=torch.float32).clamp(0.0, 1.0)
    _synchronize_cuda()
    decode_seconds = time.perf_counter() - started
    del frames, selected
    return (
        image,
        f"{decode_info} {selection_info} selected={selected_index} | decode {decode_seconds:.3f}s",
        decode_seconds,
    )


def _font(size: int, *, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(name, size=size)
    except OSError:
        return ImageFont.load_default()


def _placeholder(message: str, size: int) -> Image.Image:
    image = Image.new("RGB", (size, size), "#111827")
    draw = ImageDraw.Draw(image)
    draw.multiline_text((24, 24), message, fill="#fca5a5", font=_font(18, bold=True), spacing=8)
    return image


def _to_pil(image: torch.Tensor | None, size: int, error: str = "") -> Image.Image:
    if image is None:
        return _placeholder(error or "No image", size)
    array = (image[0].numpy() * 255.0).round().clip(0, 255).astype(np.uint8)
    source = Image.fromarray(array)
    fitted = ImageOps.contain(source, (size, size), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), "#0b0f14")
    canvas.paste(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
    return canvas


def _tensor_source_to_pil(image: Any) -> Image.Image | None:
    if not isinstance(image, torch.Tensor) or image.ndim < 3:
        return None
    value = image[0] if image.ndim == 4 else image
    if value.ndim != 3:
        return None
    if value.shape[-1] in (1, 3, 4):
        array = value.detach().to(device="cpu", dtype=torch.float32).clamp(0, 1).numpy()
    elif value.shape[0] in (1, 3, 4):
        array = value.detach().permute(1, 2, 0).to(device="cpu", dtype=torch.float32).clamp(0, 1).numpy()
    else:
        return None
    array = (array * 255.0).round().clip(0, 255).astype(np.uint8)
    if array.shape[-1] == 1:
        array = np.repeat(array, 3, axis=-1)
    return Image.fromarray(array).convert("RGB")


def _preview_data_url(image: torch.Tensor | None, edge: int = 480) -> str:
    source = _tensor_source_to_pil(image)
    if source is None:
        return ""
    source.thumbnail((edge, edge), Image.Resampling.LANCZOS)
    output = BytesIO()
    source.save(output, format="JPEG", quality=82, optimize=True)
    return f"data:image/jpeg;base64,{b64encode(output.getvalue()).decode('ascii')}"


def _send_benchmark_event(node_id: Any, payload: dict[str, Any]) -> None:
    if node_id is None:
        return
    try:
        from server import PromptServer

        server = PromptServer.instance
        server.send_sync("h3studio-benchmark-progress", {"node_id": str(node_id), **payload}, server.client_id)
    except Exception as exc:
        LOGGER.debug("H3 Studio benchmark progress event skipped: %s", exc)


def _context_header(context: H3StudioContext, width: int, include_references: bool, include_prompt: bool) -> Image.Image:
    gap = 12
    reference_size = 128
    text_width = max(44, int((width - 2 * gap) / 10))
    prompt = context.state.prompt.strip()
    prompt_note = prompt[:900] + ("…" if len(prompt) > 900 else "")
    prompt_lines = wrap(prompt_note, text_width) if include_prompt and prompt_note else []
    reference_count = len(context.images) if include_references else 0
    reference_rows = (reference_count + max(1, (width - gap) // (reference_size + gap)) - 1) // max(
        1, (width - gap) // (reference_size + gap)
    )
    reference_height = reference_rows * (reference_size + 28) if reference_count else 0
    prompt_height = 38 + len(prompt_lines) * 19 if prompt_lines else 0
    height = 50 + reference_height + prompt_height + gap
    header = Image.new("RGB", (width, height), "#10151c")
    draw = ImageDraw.Draw(header)
    draw.text((gap, 12), "Comparison context", fill="#f3f4f6", font=_font(20, bold=True))
    y = 48
    if reference_count:
        columns = max(1, (width - gap) // (reference_size + gap))
        for index, image in enumerate(context.images):
            row, column = divmod(index, columns)
            x = gap + column * (reference_size + gap)
            top = y + row * (reference_size + 28)
            source = _tensor_source_to_pil(image)
            if source is not None:
                fitted = ImageOps.contain(source, (reference_size, reference_size), Image.Resampling.LANCZOS)
                tile = Image.new("RGB", (reference_size, reference_size), "#080b10")
                tile.paste(fitted, ((reference_size - fitted.width) // 2, (reference_size - fitted.height) // 2))
            else:
                tile = _placeholder("Unavailable", reference_size)
            header.paste(tile, (x, top))
            draw.text((x, top + reference_size + 5), f"@Image{index + 1}", fill="#67e8d0", font=_font(14, bold=True))
        y += reference_height
    if prompt_lines:
        draw.text((gap, y + 4), "Original prompt", fill="#9ca3af", font=_font(14, bold=True))
        draw.multiline_text((gap, y + 26), "\n".join(prompt_lines), fill="#e5e7eb", font=_font(14), spacing=4)
    return header


def _comparison_grid(
    results: list[_ABResult],
    seed_strategy: str,
    cell_size: int,
    profile_count: int,
    generation_count: int,
    context: H3StudioContext,
    include_references: bool,
    include_prompt: bool,
) -> torch.Tensor:
    gap = 10
    header_height = 58
    label_height = 70
    columns = max(1, int(profile_count))
    rows = max(1, (len(results) + columns - 1) // columns)
    width = columns * cell_size + (columns + 1) * gap
    context_header = _context_header(context, width, include_references, include_prompt)
    matrix_height = header_height + rows * (cell_size + label_height) + (rows + 1) * gap
    height = context_header.height + matrix_height
    grid = Image.new("RGB", (width, height), "#080b10")
    grid.paste(context_header, (0, 0))
    draw = ImageDraw.Draw(grid)
    draw.text(
        (gap, context_header.height + 14),
        f"H3 Studio Benchmark Lab - {generation_count} generations - {seed_strategy}",
        fill="#e5e7eb",
        font=_font(22, bold=True),
    )

    for index, result in enumerate(results):
        row, column = divmod(index, columns)
        x = gap + column * (cell_size + gap)
        y = context_header.height + header_height + gap + row * (cell_size + label_height + gap)
        grid.paste(_to_pil(result.image, cell_size, result.error), (x, y))
        label_y = y + cell_size
        draw.rectangle((x, label_y, x + cell_size, label_y + label_height), fill="#171c24")
        requested = f"{result.spec.requested_megapixels:.2f} MP requested"
        actual = f"{result.width}x{result.height} - {result.actual_megapixels:.2f} MP actual"
        profile = short_profile_label(result.spec.profile, result.spec.accelerated)
        timing = "failed" if result.sampling_seconds is None else f"sampling {result.sampling_seconds:.2f}s"
        repeat = f" - repeat {result.spec.repeat}" if result.spec.repeat > 1 else ""
        draw.text((x + 10, label_y + 8), f"{requested} - {actual}", fill="#f3f4f6", font=_font(16, bold=True))
        draw.text(
            (x + 10, label_y + 37),
            f"seed {result.spec.seed}{repeat} - {profile} - {timing}",
            fill="#67e8d0",
            font=_font(15),
        )

    array = np.asarray(grid, dtype=np.uint8).copy()
    return torch.from_numpy(array).to(dtype=torch.float32).div_(255.0).unsqueeze(0)


def _vae_comparison_grid(items, *, cell_size: int, seed: int, sampling_seconds: float, canvas: str) -> torch.Tensor:
    gap, header_height, label_height = 10, 58, 82
    width = 2 * cell_size + 3 * gap
    height = header_height + cell_size + label_height + 2 * gap
    grid = Image.new("RGB", (width, height), "#080b10")
    draw = ImageDraw.Draw(grid)
    draw.text((gap, 14), "H3 Studio VAE A/B - identical sampled T=1 latent", fill="#e5e7eb", font=_font(22, bold=True))
    for column, (label, image, decode_seconds, note) in enumerate(items):
        x, y = gap + column * (cell_size + gap), header_height + gap
        grid.paste(_to_pil(image, cell_size), (x, y))
        label_y = y + cell_size
        draw.rectangle((x, label_y, x + cell_size, label_y + label_height), fill="#171c24")
        draw.text((x + 10, label_y + 8), label, fill="#f3f4f6", font=_font(16, bold=True))
        draw.text((x + 10, label_y + 34), f"seed {seed} - {canvas}", fill="#67e8d0", font=_font(14))
        draw.text(
            (x + 10, label_y + 57),
            f"sampling shared {sampling_seconds:.2f}s - decode {decode_seconds:.2f}s {note}",
            fill="#9ca3af",
            font=_font(13),
        )
    array = np.asarray(grid, dtype=np.uint8).copy()
    return torch.from_numpy(array).to(dtype=torch.float32).div_(255.0).unsqueeze(0)


class H3StudioABComparison:
    """Generate a guarded profile x resolution benchmark matrix."""

    CATEGORY = "H3 Studio/Benchmark"
    FUNCTION = "compare"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("comparison_grid", "comparison_report")
    DESCRIPTION = (
        "Compare one or more Base, LightX and PDD profiles across a configurable resolution matrix. The generation "
        "guard rejects accidental large runs before conditioning or model patching. Two profiles remain a simple A/B."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "h3_bundle": ("H3_STUDIO_BUNDLE",),
                "studio_context": ("H3_STUDIO_CONTEXT",),
                "comparison_kind": (
                    list(COMPARISON_KINDS),
                    {
                        "default": COMPARISON_KINDS[0],
                        "tooltip": "Compare any two sampling profiles across resolutions, or isolate decoder quality using one identical T=1 latent.",
                    },
                ),
                "profiles": (
                    "STRING",
                    {
                        "default": "base_quality_20, lightx_er_sde_4",
                        "multiline": True,
                        "tooltip": "Comma/newline-separated profile IDs or labels. Add more than two for a wider matrix.",
                    },
                ),
                "megapixels": (
                    "STRING",
                    {
                        "default": "0.40, 1.00, 2.00",
                        "tooltip": "Comma/newline-separated direct resolutions from 0.20 to 8.50 MP.",
                    },
                ),
                "repeats": ("INT", {"default": 1, "min": 1, "max": 16, "step": 1}),
                "seed_strategy": (
                    list(SEED_STRATEGIES),
                    {
                        "default": SEED_STRATEGIES[0],
                        "tooltip": "Same seed is the fairest A/B. New seed each row keeps Base/LoRA paired. New seed every image explores diversity but no longer isolates the accelerator.",
                    },
                ),
                "seed_step": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 1000000,
                        "step": 1,
                        "tooltip": "Offset added between row or image seeds. The Director seed is the matrix base seed.",
                    },
                ),
                "grid_cell_size": (
                    "INT",
                    {
                        "default": 640,
                        "min": 320,
                        "max": 1024,
                        "step": 64,
                        "tooltip": "Display size per grid cell; generation resolution is unaffected.",
                    },
                ),
                "max_generations": (
                    "INT",
                    {
                        "default": 24,
                        "min": 1,
                        "max": 128,
                        "step": 1,
                        "tooltip": "The run is rejected before execution when the matrix exceeds this count.",
                    },
                ),
                "allow_large_matrix": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Explicitly allow a matrix above your guard after checking its generation count.",
                    },
                ),
                "include_reference_context": ("BOOLEAN", {"default": True}),
                "include_original_prompt": ("BOOLEAN", {"default": True}),
                "live_cell_previews": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Show completed cells in the node. Disable to avoid preview encoding overhead.",
                    },
                ),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    def compare(
        self,
        h3_bundle,
        studio_context,
        comparison_kind: str,
        profiles: str,
        megapixels: str,
        repeats: int,
        seed_strategy: str,
        seed_step: int,
        grid_cell_size: int,
        max_generations: int,
        allow_large_matrix: bool,
        include_reference_context: bool,
        include_original_prompt: bool,
        live_cell_previews: bool,
        unique_id=None,
    ):
        if not isinstance(h3_bundle, H3StudioBundle):
            raise ValueError("Connect H3 Studio Loader's h3_bundle output.")
        if not isinstance(studio_context, H3StudioContext):
            raise ValueError("Connect H3 Studio Director's studio_context output.")
        cell_size = max(320, min(1024, int(grid_cell_size)))
        if comparison_kind == COMPARISON_KINDS[1]:
            generation = replace(studio_context.state.generation, frame_profile="image_vae_1")
            vae_context = replace(studio_context, state=replace(studio_context.state, generation=generation))
            LOGGER.info(
                "[H3 Studio - VAE A/B] Preparing one T=1 latent | seed=%d | %dx%d",
                vae_context.seed,
                vae_context.width,
                vae_context.height,
            )
            model, _generation, conditioning, latent, _final_vae, _frames, _info = H3StudioCondition().condition(
                h3_bundle, vae_context
            )
            sampled, sampling_seconds, sampling_info = _sample_latent(model, conditioning, latent, vae_context)
            original_image, original_info, original_seconds = _decode_single(sampled, h3_bundle.video_vae)
            image_vae = h3_bundle.image_vae_for_decode()
            image_image, image_info, image_seconds = _decode_single(sampled, image_vae)
            del sampled
            canvas = f"{vae_context.width}x{vae_context.height}"
            report = "\n".join(
                (
                    f"H3 Studio VAE A/B | seed={vae_context.seed} | canvas={canvas} | profile={generation.sampling_profile}",
                    f"Shared sampling={sampling_seconds:.3f}s | {sampling_info}",
                    f"Original H3 video VAE T=1 | decode={original_seconds:.3f}s | {original_info}",
                    f"Mamad8 experimental image VAE T=1 | decode={image_seconds:.3f}s | {image_info}",
                    "Both cells decode the exact same sampled latent; this isolates decoder behavior.",
                )
            )
            LOGGER.info("[H3 Studio - VAE A/B] Complete\n%s", report)
            items = (
                ("Original H3 video VAE - T=1", original_image, original_seconds, "baseline"),
                ("Mamad8 image VAE - T=1", image_image, image_seconds, "experimental"),
            )
            return _vae_comparison_grid(
                items, cell_size=cell_size, seed=vae_context.seed, sampling_seconds=sampling_seconds, canvas=canvas
            ), report
        plan = build_matrix_plan(
            profiles,
            megapixels,
            studio_context.state.generation.sampling_profile,
            base_seed=studio_context.seed,
            seed_strategy=seed_strategy,
            seed_step=seed_step,
            repeats=repeats,
            max_generations=max_generations,
            allow_large_matrix=allow_large_matrix,
            reference_count=len(studio_context.images),
            selected_route=studio_context.route.selected,
        )
        variants = plan.variants
        matrix_started = time.perf_counter()
        _send_benchmark_event(
            unique_id,
            {
                "phase": "preparing",
                "finished": 0,
                "total": plan.generation_count,
                "remaining": plan.generation_count,
                "elapsed_seconds": 0.0,
                "live_previews": bool(live_cell_previews),
            },
        )
        results: list[_ABResult] = []
        progress = None
        try:
            import comfy.utils

            progress = comfy.utils.ProgressBar(len(variants))
        except Exception:
            pass

        LOGGER.info(
            "[H3 Studio - Benchmark] Starting %d-generation matrix | base seed=%d | strategy=%s | profiles=%s | resolutions=%s",
            plan.generation_count,
            studio_context.seed,
            seed_strategy,
            ",".join(plan.profiles),
            ",".join(f"{value:g}" for value in plan.megapixels),
        )
        prepared: dict[tuple[int, int, int, str], tuple[Any, Any, Any, Any, str]] = {}
        variant_contexts = [_variant_context(studio_context, spec) for spec in variants]
        for context in variant_contexts:
            key = (context.width, context.height, context.seed, context.compile_result.native_prompt)
            if key in prepared:
                continue
            try:
                model, _generation, conditioning, latent, video_vae, _frames, _info = H3StudioCondition().condition(
                    h3_bundle,
                    context,
                )
                condition_error = ""
            except Exception as exc:
                model = conditioning = latent = video_vae = None
                condition_error = f"Conditioning failed: {exc}"
                LOGGER.exception("[H3 Studio - A/B] %s", condition_error)
            prepared[key] = (model, conditioning, latent, video_vae, condition_error)

        indexed_results: dict[int, _ABResult] = {}
        # Group by profile to avoid repeatedly swapping patched and unpatched models.
        execution_order = sorted(range(len(variants)), key=lambda index: (variants[index].profile, index))
        completed_durations: list[float] = []
        for execution_index, index in enumerate(execution_order, start=1):
            spec = variants[index]
            context = variant_contexts[index]
            label = short_profile_label(spec.profile, spec.accelerated)
            completed_before = execution_index - 1
            _send_benchmark_event(
                unique_id,
                {
                    "phase": "running",
                    "current": execution_index,
                    "finished": completed_before,
                    "total": plan.generation_count,
                    "remaining": plan.generation_count - completed_before,
                    "profile": label,
                    "profile_id": spec.profile,
                    "requested_megapixels": spec.requested_megapixels,
                    "width": context.width,
                    "height": context.height,
                    "seed": spec.seed,
                    "repeat": spec.repeat,
                    "elapsed_seconds": time.perf_counter() - matrix_started,
                },
            )
            cell_started = time.perf_counter()
            result = _ABResult(
                spec=spec,
                width=context.width,
                height=context.height,
                actual_megapixels=context.resolution.actual_megapixels,
            )
            prepared_key = (context.width, context.height, context.seed, context.compile_result.native_prompt)
            model, conditioning, latent, video_vae, condition_error = prepared[prepared_key]
            if condition_error:
                result.error = condition_error
            else:
                LOGGER.info(
                    "[H3 Studio - A/B] Running %.2f MP requested -> %dx%d actual | seed=%d | %s",
                    spec.requested_megapixels,
                    context.width,
                    context.height,
                    context.seed,
                    label,
                )
                try:
                    image, seconds, sampling_info, decode_info = _sample_one(
                        model,
                        conditioning,
                        latent,
                        video_vae,
                        context,
                    )
                    result.image = image
                    result.sampling_seconds = seconds
                    result.sampling_info = f"{sampling_info} | {decode_info}"
                    LOGGER.info("[H3 Studio - A/B] Complete | %s | sampling %.2fs", label, seconds)
                except Exception as exc:
                    result.error = f"{type(exc).__name__}: {exc}"
                    LOGGER.exception("[H3 Studio - A/B] Variant failed | %s", label)
            completed_durations.append(time.perf_counter() - cell_started)
            indexed_results[index] = result
            finished = execution_index
            if progress is not None:
                progress.update(1)
            remaining = plan.generation_count - finished
            eta_seconds = None
            if len(completed_durations) >= 2 and remaining:
                eta_seconds = sum(completed_durations) / len(completed_durations) * remaining
            _send_benchmark_event(
                unique_id,
                {
                    "phase": "complete" if not remaining else "running",
                    "current": finished,
                    "finished": finished,
                    "total": plan.generation_count,
                    "remaining": remaining,
                    "profile": label,
                    "profile_id": spec.profile,
                    "requested_megapixels": spec.requested_megapixels,
                    "width": context.width,
                    "height": context.height,
                    "seed": spec.seed,
                    "repeat": spec.repeat,
                    "elapsed_seconds": time.perf_counter() - matrix_started,
                    "eta_seconds": eta_seconds,
                    "eta_basis": "mean completed cell time" if eta_seconds is not None else "",
                    "error": result.error,
                    "preview": _preview_data_url(result.image) if live_cell_previews else "",
                },
            )

        results = [indexed_results[index] for index in range(len(variants))]

        report_lines = [
            f"H3 Studio Benchmark Lab | generations={plan.generation_count} | profiles={len(plan.profiles)} "
            f"| resolutions={len(plan.megapixels)} | repeats={plan.repeats} | base_seed={studio_context.seed} "
            f"| strategy={seed_strategy} | same prompt and references",
            "Sampling time is CUDA-synchronized time inside SamplerCustomAdvanced; conditioning and VAE decode are excluded.",
            "The first sampled cell can include lazy model initialization; later cells may benefit from warm caches.",
        ]
        for result in results:
            label = short_profile_label(result.spec.profile, result.spec.accelerated)
            timing = "FAILED" if result.sampling_seconds is None else f"{result.sampling_seconds:.3f}s"
            report_lines.append(
                f"{result.spec.requested_megapixels:.2f} MP requested -> {result.width}x{result.height} "
                f"({result.actual_megapixels:.3f} MP actual) | seed={result.spec.seed} | repeat={result.spec.repeat} "
                f"| {label} | sampling={timing}"
                + (f" | error={result.error}" if result.error else "")
            )
        report = "\n".join(report_lines)
        LOGGER.info("[H3 Studio - Benchmark] Matrix complete\n%s", report)
        return _comparison_grid(
            results,
            seed_strategy,
            cell_size,
            len(plan.profiles),
            plan.generation_count,
            studio_context,
            include_reference_context,
            include_original_prompt,
        ), report


NODE_CLASS_MAPPINGS = {
    "H3StudioABComparison": H3StudioABComparison,
    "H3StudioLazyImageSwitch": H3StudioLazyImageSwitch,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "H3StudioABComparison": "H3 Studio - Benchmark Lab",
    "H3StudioLazyImageSwitch": "H3 Studio - Normal / Benchmark Output",
}
