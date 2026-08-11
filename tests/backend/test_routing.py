from __future__ import annotations

import pytest

from h3studio.errors import RouteError
from h3studio.routing import choose_route, validate_generation_contract


@pytest.mark.parametrize(
    ("mode", "count", "route"),
    [
        ("text_to_image", 0, "fl2va"),
        ("image_to_image", 1, "fl2va"),
        ("reference_edit", 2, "ref2va"),
    ],
)
def test_auto_routes(mode: str, count: int, route: str) -> None:
    assert choose_route("auto", mode, count).selected == route


def test_forced_ref2va_t2i_is_rejected() -> None:
    with pytest.raises(RouteError, match="incompatible"):
        choose_route("ref2va", "text_to_image", 0)


def test_forced_fl2va_reference_edit_is_rejected() -> None:
    with pytest.raises(RouteError, match="incompatible"):
        choose_route("fl2va", "reference_edit", 3)


@pytest.mark.parametrize("mode", ["image_to_image", "reference_edit"])
def test_reference_modes_reject_zero_references(mode: str) -> None:
    with pytest.raises(RouteError, match="requires at least one"):
        validate_generation_contract(mode, "auto", "base_quality_20", 0)


def test_pdd_rejects_zero_references_and_forced_fl2va() -> None:
    with pytest.raises(RouteError, match="PDD REF2VA requires"):
        validate_generation_contract("auto", "auto", "pdd_ref2va_4_900", 0)
    with pytest.raises(RouteError, match="forced FL2VA"):
        validate_generation_contract("reference_edit", "fl2va", "pdd_ref2va_4_900", 1)


def test_pdd_accepts_auto_or_reference_edit_with_references() -> None:
    validate_generation_contract("auto", "auto", "pdd_ref2va_4_900", 1)
    validate_generation_contract("reference_edit", "ref2va", "pdd_ref2va_4_900", 2)


def test_invalid_route_raises() -> None:
    with pytest.raises(RouteError):
        choose_route("magic", "text_to_image", 0)


def test_invalid_mode_cannot_auto_route() -> None:
    with pytest.raises(RouteError):
        choose_route("auto", "video", 0)


def test_negative_reference_count_raises() -> None:
    with pytest.raises(RouteError):
        choose_route("auto", "text_to_image", -1)
