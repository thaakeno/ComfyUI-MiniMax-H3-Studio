from __future__ import annotations

from h3studio.benchmark import (
    SEED_STRATEGIES,
    build_ab_variants,
    build_seed_plan,
    resolve_accelerator,
    short_profile_label,
)


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


def test_director_base_profile_is_valid_instead_of_crashing_after_analysis() -> None:
    assert resolve_accelerator("Director selected accelerator", "base_quality_20") == "base_quality_20"


def test_ab_supports_lora_against_lora() -> None:
    variants = build_ab_variants(
        "LightX v0.1 - ER-SDE 4",
        "PDD REF2VA - 4-step - ckpt 900",
        "base_quality_20",
    )
    assert {item.profile for item in variants} == {"lightx_er_sde_4", "pdd_ref2va_4_900"}
    assert all(item.accelerated for item in variants)


def test_ab_labels_say_whether_a_lora_is_active() -> None:
    assert short_profile_label("base_quality_20", False).startswith("No LoRA")
    assert short_profile_label("lightx_er_sde_4", True).startswith("LoRA")


def test_ab_seed_strategies_preserve_their_comparison_contracts() -> None:
    assert build_seed_plan(42, SEED_STRATEGIES[0]) == (42, 42, 42, 42, 42, 42)
    assert build_seed_plan(42, SEED_STRATEGIES[1], 10) == (42, 42, 52, 52, 62, 62)
    assert build_seed_plan(42, SEED_STRATEGIES[2]) == (42, 43, 44, 45, 46, 47)


def test_ab_variants_store_the_seed_shown_for_each_cell() -> None:
    variants = build_ab_variants(
        "Base Quality - RES 20",
        "LightX v0.1 - ER-SDE 4",
        "base_quality_20",
        100,
        SEED_STRATEGIES[1],
        5,
    )
    assert [item.seed for item in variants] == [100, 100, 105, 105, 110, 110]
