from __future__ import annotations

import pytest

from h3studio.benchmark import build_ab_variants, resolve_accelerator, short_profile_label


def test_ab_matrix_builds_resolution_rows_with_baseline_then_accelerator() -> None:
    variants = build_ab_variants(
        "Base Quality - RES 20",
        "Director selected accelerator",
        "pdd_ref2va_4_900",
    )

    assert len(variants) == 6
    assert [item.requested_megapixels for item in variants] == [0.4, 0.4, 1.0, 1.0, 2.0, 2.0]
    assert [item.accelerated for item in variants] == [False, True, False, True, False, True]
    assert variants[0].profile == "base_quality_20"
    assert variants[1].profile == "pdd_ref2va_4_900"


def test_director_base_profile_requires_an_explicit_accelerator() -> None:
    with pytest.raises(ValueError, match="Choose LightX or PDD explicitly"):
        resolve_accelerator("Director selected accelerator", "base_quality_20")


def test_ab_labels_say_whether_a_lora_is_active() -> None:
    assert short_profile_label("base_quality_20", False).startswith("No LoRA")
    assert short_profile_label("lightx_er_sde_4", True).startswith("LoRA")
