"""Optional reference-versus-result presentation sheet."""

from __future__ import annotations

from typing import Any

try:  # ComfyUI supplies this at runtime; pure helpers remain importable in tests.
    import nodes as comfy_nodes
except ImportError:  # pragma: no cover
    comfy_nodes = None

from ..context import H3StudioContext


def _font(size: int, *, bold: bool = False):
    from PIL import ImageFont

    names = ("DejaVuSans-Bold.ttf", "Arial Bold.ttf") if bold else ("DejaVuSans.ttf", "Arial.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _contain_on(image, box, size):
    from PIL import Image, ImageOps

    fitted = ImageOps.contain(image.convert("RGB"), size, Image.Resampling.LANCZOS)
    x = box[0] + (size[0] - fitted.width) // 2
    y = box[1] + (size[1] - fitted.height) // 2
    return fitted, (x, y)


def comparison_layout(reference_count: int) -> dict[str, Any]:
    count = max(0, int(reference_count))
    left = (64, 128, 456, 930)
    gap = 12
    cell_height = 0 if count == 0 else max(76, (left[3] - left[1] - gap * (count + 1)) // count)
    return {
        "canvas": (1600, 1000),
        "references": left,
        "result": (520, 128, 1536, 930),
        "gap": gap,
        "cell_height": cell_height,
    }


def compose_comparison_sheet(final_image, references, labels, metadata: str):
    """Build one calm, legible 1600x1000 comparison image from PIL inputs."""

    from PIL import Image, ImageDraw

    layout = comparison_layout(len(references))
    canvas = Image.new("RGB", layout["canvas"], (13, 16, 18))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((32, 28, 1568, 972), radius=24, fill=(21, 26, 29), outline=(54, 68, 72), width=2)
    draw.text((64, 54), "REFERENCE INPUTS", font=_font(22, bold=True), fill=(116, 224, 204))
    draw.text((520, 54), "GENERATED EDIT", font=_font(22, bold=True), fill=(255, 255, 255))
    draw.text((520, 87), metadata, font=_font(15), fill=(159, 171, 176))

    left = layout["references"]
    final_box = layout["result"]
    draw.rounded_rectangle(left, radius=16, fill=(14, 18, 20), outline=(45, 57, 61), width=2)
    draw.rounded_rectangle(final_box, radius=16, fill=(9, 12, 14), outline=(56, 72, 76), width=2)

    if references:
        gap = layout["gap"]
        cell_height = layout["cell_height"]
        y = left[1] + gap
        for reference, label in zip(references, labels, strict=False):
            bottom = min(left[3] - gap, y + cell_height)
            draw.rounded_rectangle((left[0] + gap, y, left[2] - gap, bottom), radius=10, fill=(25, 31, 34))
            draw.text((left[0] + 24, y + 10), label, font=_font(14, bold=True), fill=(229, 237, 237))
            image_top = y + 36
            image_height = max(20, bottom - image_top - 10)
            fitted, position = _contain_on(reference, (left[0] + 20, image_top), (left[2] - left[0] - 40, image_height))
            canvas.paste(fitted, position)
            y = bottom + gap
    else:
        draw.text((126, 500), "No reference images", font=_font(18), fill=(127, 141, 146))

    fitted_final, final_position = _contain_on(
        final_image,
        (final_box[0] + 18, final_box[1] + 18),
        (final_box[2] - final_box[0] - 36, final_box[3] - final_box[1] - 36),
    )
    canvas.paste(fitted_final, final_position)
    return canvas


def _tensor_to_pil(value):
    from PIL import Image

    pixels = value[0].detach().float().clamp(0, 1).mul(255).byte().cpu().numpy()
    return Image.fromarray(pixels, mode="RGB")


def build_comparison_tensor(images, context: H3StudioContext):
    import numpy
    import torch

    final_image = _tensor_to_pil(images)
    enabled = context.state.enabled_references
    reference_images = []
    labels = []
    for reference in enabled:
        image_index = int(reference.ordinal) - 1
        if image_index < 0 or image_index >= len(context.images):
            continue
        reference_images.append(_tensor_to_pil(context.images[image_index]))
        role = reference.effective_role.replace("_", " ").upper()
        labels.append(f"@Image{reference.ordinal}  ·  {role}")
    metadata = (
        f"Seed {context.seed}  ·  {context.width} × {context.height}  ·  "
        f"{context.state.generation.sampling_profile}"
    )
    sheet = compose_comparison_sheet(final_image, reference_images, labels, metadata)
    array = numpy.asarray(sheet, dtype=numpy.float32) / 255.0
    return torch.from_numpy(array).unsqueeze(0)


_PreviewImageBase = comfy_nodes.PreviewImage if comfy_nodes is not None else object


class H3StudioComparisonView(_PreviewImageBase):
    """Show a reference-left/result-right sheet only when enabled in Director."""

    CATEGORY = "H3 Studio/Output"
    FUNCTION = "compare"
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    DESCRIPTION = "Optional presentation sheet controlled by Director · Comparison image."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "studio_context": ("H3_STUDIO_CONTEXT",),
            }
        }

    def compare(self, images, studio_context, prompt=None, extra_pnginfo=None):
        if not isinstance(studio_context, H3StudioContext):
            raise ValueError("Connect H3 Studio Director's studio_context output.")
        if not bool(studio_context.state.ui.get("comparison_enabled", False)):
            return {"ui": {"images": []}}
        sheet = build_comparison_tensor(images, studio_context)
        return super().save_images(sheet, "H3StudioComparison", prompt, extra_pnginfo)


NODE_CLASS_MAPPINGS = {"H3StudioComparisonView": H3StudioComparisonView}
NODE_DISPLAY_NAME_MAPPINGS = {"H3StudioComparisonView": "H3 Studio · Reference Comparison"}
