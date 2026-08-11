"""Aspect-ratio and megapixel resolution planning for H3 still images."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .constants import (
    ASPECT_RATIOS,
    CANVAS_MULTIPLE,
    DEFAULT_HEIGHT,
    DEFAULT_MEGAPIXELS,
    DEFAULT_WIDTH,
    MAX_MEGAPIXELS,
    MIN_MEGAPIXELS,
    NATIVE_MAX_PIXELS,
)
from .errors import ResolutionError


def round_to_multiple(value: float, multiple: int = CANVAS_MULTIPLE) -> int:
    if not math.isfinite(float(value)):
        raise ResolutionError("Resolution contains a non-finite value.")
    return max(multiple, int(round(float(value) / multiple)) * multiple)


def floor_to_multiple(value: float, multiple: int = CANVAS_MULTIPLE) -> int:
    if not math.isfinite(float(value)):
        raise ResolutionError("Resolution contains a non-finite value.")
    return max(multiple, int(math.floor(float(value) / multiple)) * multiple)


def parse_aspect_ratio(value: str, custom_width: int = DEFAULT_WIDTH, custom_height: int = DEFAULT_HEIGHT) -> float:
    text = str(value or "1:1").strip().lower()
    if text in ASPECT_RATIOS and text != "custom":
        width, height = ASPECT_RATIOS[text]
        return width / height
    if text == "custom":
        if custom_width <= 0 or custom_height <= 0:
            raise ResolutionError("Custom width and height must be positive.")
        return custom_width / custom_height
    if ":" in text:
        left, right = text.split(":", 1)
        try:
            width = float(left)
            height = float(right)
        except ValueError as exc:
            raise ResolutionError(f"Invalid aspect ratio {value!r}.") from exc
        if width <= 0 or height <= 0:
            raise ResolutionError("Aspect-ratio components must be positive.")
        return width / height
    try:
        ratio = float(text)
    except ValueError as exc:
        raise ResolutionError(f"Invalid aspect ratio {value!r}.") from exc
    if ratio <= 0:
        raise ResolutionError("Aspect ratio must be positive.")
    return ratio


def label_for_ratio(ratio: float, tolerance: float = 0.015) -> str:
    best_label = "custom"
    best_error = math.inf
    for label, pair in ASPECT_RATIOS.items():
        if label == "custom":
            continue
        candidate = pair[0] / pair[1]
        error = abs(candidate - ratio) / candidate
        if error < best_error:
            best_label, best_error = label, error
    return best_label if best_error <= tolerance else "custom"


@dataclass(frozen=True, slots=True)
class ResolutionPlan:
    width: int
    height: int
    requested_megapixels: float
    actual_megapixels: float
    aspect_ratio: str
    ratio: float
    capped: bool
    cap_pixels: int | None
    multiple: int = CANVAS_MULTIPLE

    @property
    def pixels(self) -> int:
        return self.width * self.height

    @property
    def orientation(self) -> str:
        if self.width == self.height:
            return "square"
        return "landscape" if self.width > self.height else "portrait"

    def as_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "pixels": self.pixels,
            "requested_megapixels": self.requested_megapixels,
            "actual_megapixels": self.actual_megapixels,
            "aspect_ratio": self.aspect_ratio,
            "ratio": self.ratio,
            "orientation": self.orientation,
            "capped": self.capped,
            "cap_pixels": self.cap_pixels,
            "multiple": self.multiple,
        }

    def summary(self) -> str:
        cap = " · capped" if self.capped else ""
        return f"{self.width}×{self.height} · {self.actual_megapixels:.3f} MP · {self.aspect_ratio}{cap}"


def plan_resolution(
    aspect_ratio: str = "1:1",
    megapixels: float = DEFAULT_MEGAPIXELS,
    *,
    custom_width: int = DEFAULT_WIDTH,
    custom_height: int = DEFAULT_HEIGHT,
    cap_native: bool = False,
    cap_pixels: int | None = NATIVE_MAX_PIXELS,
    multiple: int = CANVAS_MULTIPLE,
) -> ResolutionPlan:
    try:
        requested_mp = float(megapixels)
    except (TypeError, ValueError) as exc:
        raise ResolutionError("Megapixels must be numeric.") from exc
    if not math.isfinite(requested_mp):
        raise ResolutionError("Megapixels must be finite.")
    requested_mp = min(MAX_MEGAPIXELS, max(MIN_MEGAPIXELS, requested_mp))
    ratio = parse_aspect_ratio(aspect_ratio, custom_width, custom_height)
    target_pixels = requested_mp * 1_000_000
    effective_cap = int(cap_pixels) if cap_native and cap_pixels else None
    capped = bool(effective_cap and target_pixels > effective_cap)
    if effective_cap:
        target_pixels = min(target_pixels, effective_cap)

    nominal_width = math.sqrt(target_pixels * ratio)
    nominal_height = math.sqrt(target_pixels / ratio)
    width = round_to_multiple(nominal_width, multiple)
    height = round_to_multiple(nominal_height, multiple)

    if effective_cap and width * height > effective_cap:
        candidates: list[tuple[float, int, int]] = []
        for dw in (0, -multiple, multiple):
            for dh in (0, -multiple, multiple):
                candidate_width = max(multiple, width + dw)
                candidate_height = max(multiple, height + dh)
                pixels = candidate_width * candidate_height
                if pixels > effective_cap:
                    continue
                ratio_error = abs(candidate_width / candidate_height - ratio) / ratio
                area_error = abs(pixels - target_pixels) / target_pixels
                candidates.append((ratio_error * 4 + area_error, candidate_width, candidate_height))
        if candidates:
            _, width, height = min(candidates)
        else:
            scale = math.sqrt(effective_cap / (width * height))
            width = floor_to_multiple(width * scale, multiple)
            height = floor_to_multiple(height * scale, multiple)
        capped = True

    actual_mp = width * height / 1_000_000
    ratio_label = (
        aspect_ratio if aspect_ratio in ASPECT_RATIOS and aspect_ratio != "custom" else label_for_ratio(width / height)
    )
    return ResolutionPlan(
        width=width,
        height=height,
        requested_megapixels=requested_mp,
        actual_megapixels=actual_mp,
        aspect_ratio=ratio_label,
        ratio=width / height,
        capped=capped,
        cap_pixels=effective_cap,
        multiple=multiple,
    )


def plan_from_dimensions(width: int, height: int, *, cap_native: bool = False) -> ResolutionPlan:
    if width <= 0 or height <= 0:
        raise ResolutionError("Width and height must be positive.")
    aligned_width = round_to_multiple(width)
    aligned_height = round_to_multiple(height)
    megapixels = aligned_width * aligned_height / 1_000_000
    return plan_resolution(
        "custom",
        megapixels,
        custom_width=aligned_width,
        custom_height=aligned_height,
        cap_native=cap_native,
    )
