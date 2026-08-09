"""One-click, same-seed MiniMax H3 resolution and acceleration comparison."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..benchmark import ACCELERATOR_PROFILES, BASELINE_PROFILES, ABVariantSpec, build_ab_variants, short_profile_label
from ..context import H3StudioContext
from .director import H3StudioCondition, H3StudioContextSamplingPreset
from .image_runtime import H3StudioDecode, H3StudioFrameSelector
from .loader import H3StudioBundle

LOGGER = logging.getLogger(__name__)
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
    generation = replace(context.state.generation, megapixels=spec.requested_megapixels, sampling_profile=spec.profile)
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
    from comfy_extras.nodes_custom_sampler import BasicGuider, RandomNoise, SamplerCustomAdvanced

    shifted_model, sampler, sigmas, sampling_info = H3StudioContextSamplingPreset().build(model, context)
    guider = _outputs(BasicGuider.get_guider(shifted_model, conditioning))[0]
    noise = _outputs(RandomNoise.get_noise(context.seed))[0]
    _synchronize_cuda()
    started = time.perf_counter()
    sampled = _outputs(SamplerCustomAdvanced.sample(noise, guider, sampler, sigmas, latent))[0]
    _synchronize_cuda()
    sampling_seconds = time.perf_counter() - started

    frames, _count, decode_info, recommended_index = H3StudioDecode().decode(sampled, video_vae)
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
    del sampled, frames, selected
    return image, sampling_seconds, sampling_info, f"{decode_info} {selection_info} selected={selected_index}"


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


def _comparison_grid(results: list[_ABResult], seed: int, cell_size: int) -> torch.Tensor:
    gap = 10
    header_height = 58
    label_height = 70
    rows, columns = 3, 2
    width = columns * cell_size + (columns + 1) * gap
    height = header_height + rows * (cell_size + label_height) + (rows + 1) * gap
    grid = Image.new("RGB", (width, height), "#080b10")
    draw = ImageDraw.Draw(grid)
    draw.text(
        (gap, 14),
        f"H3 Studio A/B Matrix - same prompt, references and seed {seed}",
        fill="#e5e7eb",
        font=_font(22, bold=True),
    )

    for index, result in enumerate(results):
        row, column = divmod(index, columns)
        x = gap + column * (cell_size + gap)
        y = header_height + gap + row * (cell_size + label_height + gap)
        grid.paste(_to_pil(result.image, cell_size, result.error), (x, y))
        label_y = y + cell_size
        draw.rectangle((x, label_y, x + cell_size, label_y + label_height), fill="#171c24")
        requested = f"{result.spec.requested_megapixels:.2f} MP requested"
        actual = f"{result.width}x{result.height} - {result.actual_megapixels:.2f} MP actual"
        profile = short_profile_label(result.spec.profile, result.spec.accelerated)
        timing = "failed" if result.sampling_seconds is None else f"sampling {result.sampling_seconds:.2f}s"
        draw.text((x + 10, label_y + 8), f"{requested} - {actual}", fill="#f3f4f6", font=_font(16, bold=True))
        draw.text((x + 10, label_y + 37), f"{profile} - {timing}", fill="#67e8d0", font=_font(15))

    array = np.asarray(grid, dtype=np.uint8).copy()
    return torch.from_numpy(array).to(dtype=torch.float32).div_(255.0).unsqueeze(0)


class H3StudioABComparison:
    """Generate a six-cell, same-seed resolution and LoRA comparison grid."""

    CATEGORY = "H3 Studio/Benchmark"
    FUNCTION = "compare"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("comparison_grid", "comparison_report")
    DESCRIPTION = (
        "Runs 0.40, 1.00 and 2.00 MP at one fixed seed. Each resolution compares a native no-LoRA Base profile "
        "against the selected LightX/PDD accelerator, measures the synchronized sampling call, and produces one "
        "labeled grid. This is intentionally expensive: enabling it queues six complete generations."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "h3_bundle": ("H3_STUDIO_BUNDLE",),
                "studio_context": ("H3_STUDIO_CONTEXT",),
                "enabled": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "OFF is instant. ON runs all six same-seed benchmark generations."},
                ),
                "baseline_profile": (
                    list(BASELINE_PROFILES.keys()),
                    {"default": "Base Quality - RES 20", "tooltip": "No-LoRA reference column."},
                ),
                "accelerator_profile": (
                    list(ACCELERATOR_PROFILES.keys()),
                    {"default": "Director selected accelerator", "tooltip": "LoRA/PDD comparison column."},
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
            }
        }

    def compare(
        self,
        h3_bundle,
        studio_context,
        enabled: bool,
        baseline_profile: str,
        accelerator_profile: str,
        grid_cell_size: int,
    ):
        if not isinstance(h3_bundle, H3StudioBundle):
            raise ValueError("Connect H3 Studio Loader's h3_bundle output.")
        if not isinstance(studio_context, H3StudioContext):
            raise ValueError("Connect H3 Studio Director's studio_context output.")
        cell_size = max(320, min(1024, int(grid_cell_size)))
        if not enabled:
            disabled = _placeholder("A/B Matrix is disabled\nEnable it to run six same-seed generations.", cell_size)
            array = np.asarray(disabled, dtype=np.uint8).copy()
            image = torch.from_numpy(array).to(dtype=torch.float32).div_(255.0).unsqueeze(0)
            return image, "A/B Matrix disabled; no model, conditioning, sampling, or decode work ran."

        variants = build_ab_variants(
            baseline_profile,
            accelerator_profile,
            studio_context.state.generation.sampling_profile,
        )
        results: list[_ABResult] = []
        progress = None
        try:
            import comfy.utils

            progress = comfy.utils.ProgressBar(len(variants))
        except Exception:
            pass

        LOGGER.info(
            "[H3 Studio - A/B] Starting six-run matrix | seed=%d | baseline=%s | accelerator=%s",
            studio_context.seed,
            variants[0].profile,
            variants[1].profile,
        )
        for row in range(3):
            row_specs = variants[row * 2 : row * 2 + 2]
            condition_context = _variant_context(studio_context, row_specs[0])
            try:
                model, _generation, conditioning, latent, video_vae, _frames, _info = H3StudioCondition().condition(
                    h3_bundle,
                    condition_context,
                )
                condition_error = ""
            except Exception as exc:
                model = conditioning = latent = video_vae = None
                condition_error = f"Conditioning failed: {exc}"
                LOGGER.exception("[H3 Studio - A/B] %s", condition_error)

            for spec in row_specs:
                context = _variant_context(studio_context, spec)
                result = _ABResult(
                    spec=spec,
                    width=context.width,
                    height=context.height,
                    actual_megapixels=context.resolution.actual_megapixels,
                )
                if condition_error:
                    result.error = condition_error
                else:
                    label = short_profile_label(spec.profile, spec.accelerated)
                    LOGGER.info(
                        "[H3 Studio - A/B] Running %.2f MP requested -> %dx%d actual | %s",
                        spec.requested_megapixels,
                        context.width,
                        context.height,
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
                results.append(result)
                if progress is not None:
                    progress.update(1)

        report_lines = [
            f"H3 Studio A/B Matrix | seed={studio_context.seed} | same prompt and references",
            "Sampling time is CUDA-synchronized time inside SamplerCustomAdvanced; conditioning and VAE decode are excluded.",
            "The first sampled cell can include lazy model initialization; later cells may benefit from warm caches.",
        ]
        for result in results:
            label = short_profile_label(result.spec.profile, result.spec.accelerated)
            timing = "FAILED" if result.sampling_seconds is None else f"{result.sampling_seconds:.3f}s"
            report_lines.append(
                f"{result.spec.requested_megapixels:.2f} MP requested -> {result.width}x{result.height} "
                f"({result.actual_megapixels:.3f} MP actual) | {label} | sampling={timing}"
                + (f" | error={result.error}" if result.error else "")
            )
        report = "\n".join(report_lines)
        LOGGER.info("[H3 Studio - A/B] Matrix complete\n%s", report)
        return _comparison_grid(results, studio_context.seed, cell_size), report


NODE_CLASS_MAPPINGS = {"H3StudioABComparison": H3StudioABComparison}
NODE_DISPLAY_NAME_MAPPINGS = {"H3StudioABComparison": "H3 Studio - Same-Seed A/B Matrix"}
