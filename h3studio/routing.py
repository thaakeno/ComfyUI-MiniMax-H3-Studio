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


def choose_route(requested: str, mode: str, reference_count: int) -> RouteDecision:
    if reference_count < 0:
        raise RouteError("Reference count cannot be negative.")
    requested = str(requested or ROUTE_AUTO).strip().lower()
    if requested not in {ROUTE_AUTO, ROUTE_FL2VA, ROUTE_REF2VA}:
        raise RouteError(f"Unknown H3 route {requested!r}.")

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

    if requested == ROUTE_REF2VA and reference_count == 0:
        return RouteDecision(
            requested,
            ROUTE_REF2VA,
            mode,
            reference_count,
            "forced REF2VA without images; retained for Lightning comparison",
            experimental=True,
        )
    if requested == ROUTE_FL2VA and mode == MODE_REFERENCE_EDIT and reference_count > 1:
        return RouteDecision(
            requested,
            ROUTE_FL2VA,
            mode,
            reference_count,
            "forced FL2VA cannot consume the complete ordered reference set",
            experimental=True,
        )
    return RouteDecision(requested, requested, mode, reference_count, "explicit user selection")
