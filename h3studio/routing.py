"""Explicit selection of the H3 conditioning model path."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    MODE_IMAGE_TO_IMAGE,
    MODE_REFERENCE_EDIT,
    MODE_TEXT_TO_IMAGE,
    ROUTE_AUTO,
    ROUTE_FL2VA,
    ROUTE_REF2VA,
)
from .errors import RouteError


@dataclass(frozen=True, slots=True)
class RouteDecision:
    requested: str
    selected: str
    mode: str
    reference_count: int
    reason: str
    experimental: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "requested": self.requested,
            "selected": self.selected,
            "mode": self.mode,
            "reference_count": self.reference_count,
            "reason": self.reason,
            "experimental": self.experimental,
        }

    def summary(self) -> str:
        suffix = " · experimental" if self.experimental else ""
        return f"{self.mode} → {self.selected} · {self.reason}{suffix}"


def validate_generation_contract(
    mode: str,
    requested_route: str,
    sampling_profile: str,
    reference_count: int,
) -> None:
    """Reject impossible Studio requests before analyzers or models are invoked."""

    if reference_count < 0:
        raise RouteError("Reference count cannot be negative.")
    mode = str(mode or "auto").strip().lower()
    requested_route = str(requested_route or ROUTE_AUTO).strip().lower()
    is_pdd = str(sampling_profile or "").startswith("pdd_ref2va_")
    if mode not in {"auto", MODE_TEXT_TO_IMAGE, MODE_IMAGE_TO_IMAGE, MODE_REFERENCE_EDIT}:
        raise RouteError(f"Unsupported H3 generation mode {mode!r}.")
    if requested_route not in {ROUTE_AUTO, ROUTE_FL2VA, ROUTE_REF2VA}:
        raise RouteError(f"Unknown H3 route {requested_route!r}.")
    if mode == MODE_IMAGE_TO_IMAGE and reference_count == 0:
        raise RouteError("Image-to-image requires at least one enabled reference image.")
    if mode == MODE_REFERENCE_EDIT and reference_count == 0:
        raise RouteError("Reference mix/edit requires at least one enabled reference image.")
    if is_pdd and reference_count == 0:
        raise RouteError("PDD REF2VA requires at least one enabled reference image.")
    if is_pdd and mode in {MODE_TEXT_TO_IMAGE, MODE_IMAGE_TO_IMAGE}:
        raise RouteError("PDD REF2VA supports reference mix/edit; use Auto or Reference mix/edit mode.")
    if is_pdd and requested_route == ROUTE_FL2VA:
        raise RouteError("PDD is trained for REF2VA and cannot run on a forced FL2VA route.")

    effective_mode = mode
    if mode == "auto":
        if reference_count == 0:
            effective_mode = MODE_TEXT_TO_IMAGE
        elif reference_count == 1 and not is_pdd:
            effective_mode = MODE_IMAGE_TO_IMAGE
        else:
            effective_mode = MODE_REFERENCE_EDIT
    expected_route = ROUTE_REF2VA if effective_mode == MODE_REFERENCE_EDIT else ROUTE_FL2VA
    if requested_route != ROUTE_AUTO and requested_route != expected_route:
        raise RouteError(
            f"Forced {requested_route.upper()} is incompatible with {effective_mode.replace('_', ' ')} mode; use Auto."
        )


def choose_route(requested: str, mode: str, reference_count: int) -> RouteDecision:
    if reference_count < 0:
        raise RouteError("Reference count cannot be negative.")
    requested = str(requested or ROUTE_AUTO).strip().lower()
    if requested not in {ROUTE_AUTO, ROUTE_FL2VA, ROUTE_REF2VA}:
        raise RouteError(f"Unknown H3 route {requested!r}.")
    validate_generation_contract(mode, requested, "", reference_count)

    if requested == ROUTE_AUTO:
        if mode == MODE_TEXT_TO_IMAGE:
            return RouteDecision(requested, ROUTE_FL2VA, mode, reference_count, "native empty/keyframe conditioning")
        if mode == MODE_IMAGE_TO_IMAGE:
            return RouteDecision(
                requested, ROUTE_FL2VA, mode, reference_count, "source image used as first-frame anchor"
            )
        if mode == MODE_REFERENCE_EDIT:
            return RouteDecision(requested, ROUTE_REF2VA, mode, reference_count, "ordered full-reference conditioning")
        raise RouteError(f"Cannot auto-route unsupported mode {mode!r}.")

    return RouteDecision(requested, requested, mode, reference_count, "explicit user selection")
