from __future__ import annotations

import math

import pytest

from h3studio.constants import NATIVE_MAX_PIXELS, UHD_4K_MEGAPIXELS
from h3studio.errors import ResolutionError
from h3studio.resolution import (
    label_for_ratio,
    parse_aspect_ratio,
    plan_from_dimensions,
    plan_resolution,
    round_to_multiple,
)


@pytest.mark.parametrize("value", [1, 31, 32, 47, 1024.2, 1344])
def test_round_to_multiple(value: float) -> None:
    result = round_to_multiple(value)
    assert result >= 32
    assert result % 32 == 0


@pytest.mark.parametrize(
    ("label", "ratio"),
    [("1:1", 1.0), ("16:9", 16 / 9), ("9:16", 9 / 16), ("3:4", 0.75), ("21:9", 21 / 9)],
)
def test_parse_known_aspect_ratios(label: str, ratio: float) -> None:
    assert parse_aspect_ratio(label) == pytest.approx(ratio)


def test_parse_custom_ratio_uses_dimensions() -> None:
    assert parse_aspect_ratio("custom", 1200, 800) == pytest.approx(1.5)


@pytest.mark.parametrize("value", ["0:1", "bad", "1:0", "-2:3"])
def test_invalid_ratio_raises(value: str) -> None:
    with pytest.raises(ResolutionError):
        parse_aspect_ratio(value)


@pytest.mark.parametrize("ratio", ["1:1", "4:5", "5:4", "3:4", "4:3", "2:3", "3:2", "9:16", "16:9"])
def test_plan_is_aligned_and_close_to_requested_area(ratio: str) -> None:
    plan = plan_resolution(ratio, 0.8, cap_native=False)
    assert plan.width % 32 == 0
    assert plan.height % 32 == 0
    assert plan.actual_megapixels == pytest.approx(0.8, abs=0.05)


def test_direct_resolution_is_the_default() -> None:
    plan = plan_resolution("1:1", 2.0)
    assert plan.width == 1408
    assert plan.height == 1408
    assert plan.actual_megapixels == pytest.approx(1.982464)
    assert plan.pixels > NATIVE_MAX_PIXELS
    assert not plan.capped


def test_one_and_two_megapixel_requests_no_longer_collapse_to_same_canvas() -> None:
    one_mp = plan_resolution("1:1", 1.0)
    two_mp = plan_resolution("1:1", 2.0)
    assert (one_mp.width, one_mp.height) == (992, 992)
    assert (two_mp.width, two_mp.height) == (1408, 1408)
    assert two_mp.pixels > one_mp.pixels * 1.9


def test_native_cap_is_still_available_explicitly() -> None:
    plan = plan_resolution("16:9", 2.0, cap_native=True)
    assert plan.pixels <= NATIVE_MAX_PIXELS
    assert plan.capped


def test_native_cap_can_be_disabled() -> None:
    plan = plan_resolution("1:1", 2.0, cap_native=False)
    assert plan.pixels > NATIVE_MAX_PIXELS
    assert not plan.capped


def test_direct_4k_class_16_9_reaches_h3_canvas_without_upscale() -> None:
    plan = plan_resolution("16:9", UHD_4K_MEGAPIXELS)
    # 3840 is already divisible by 32; 2160 is not, so H3 alignment yields
    # 2176. This is a genuine ~8.36 MP model canvas, not a post-upscale.
    assert plan.width == 3840
    assert plan.height == 2176
    assert plan.width % 32 == 0
    assert plan.height % 32 == 0
    assert plan.actual_megapixels == pytest.approx(8.35584)
    assert plan.actual_megapixels > 8.0
    assert not plan.capped


def test_direct_four_megapixel_square_is_not_native_capped() -> None:
    plan = plan_resolution("1:1", 4.0)
    assert (plan.width, plan.height) == (1984, 1984)
    assert plan.actual_megapixels == pytest.approx(3.936256)
    assert not plan.capped


def test_plan_preserves_orientation() -> None:
    assert plan_resolution("9:16").orientation == "portrait"
    assert plan_resolution("16:9").orientation == "landscape"
    assert plan_resolution("1:1").orientation == "square"


def test_plan_from_dimensions_aligns() -> None:
    plan = plan_from_dimensions(1001, 777)
    assert plan.width % 32 == 0
    assert plan.height % 32 == 0
    assert plan.orientation == "landscape"


def test_label_for_ratio() -> None:
    assert label_for_ratio(1.0) == "1:1"
    assert label_for_ratio(16 / 9) == "16:9"
    assert label_for_ratio(math.pi) == "custom"


def test_resolution_summary_is_readable() -> None:
    summary = plan_resolution("1:1", 1.0).summary()
    assert "×" in summary
    assert "MP" in summary
    assert "1:1" in summary
