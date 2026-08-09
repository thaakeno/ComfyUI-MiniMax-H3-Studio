from __future__ import annotations

import pytest

from h3studio.errors import RouteError
from h3studio.routing import choose_route


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


def test_forced_ref2va_t2i_is_marked_experimental() -> None:
    decision = choose_route("ref2va", "text_to_image", 0)
    assert decision.selected == "ref2va"
    assert decision.experimental


def test_forced_fl2va_multi_reference_is_marked_experimental() -> None:
    decision = choose_route("fl2va", "reference_edit", 3)
    assert decision.experimental


def test_invalid_route_raises() -> None:
    with pytest.raises(RouteError):
        choose_route("magic", "text_to_image", 0)


def test_invalid_mode_cannot_auto_route() -> None:
    with pytest.raises(RouteError):
        choose_route("auto", "video", 0)


def test_negative_reference_count_raises() -> None:
    with pytest.raises(RouteError):
        choose_route("auto", "text_to_image", -1)
