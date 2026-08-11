from __future__ import annotations

from h3studio.benchmark import (
    SEED_STRATEGIES,
    build_ab_variants,
    build_matrix_plan,
    build_seed_plan,
    parse_megapixel_list,
    parse_profile_list,
    resolve_accelerator,
    short_profile_label,
)
from h3studio.nodes.lazy_switch import H3StudioLazyImageSwitch


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


def test_matrix_accepts_more_than_two_profiles_and_reports_exact_launch_count() -> None:
    plan = build_matrix_plan(
        "base_quality_20, lightx_er_sde_4, lightx_sa_solver_4",
        "0.4, 1.0",
        "base_quality_20",
        repeats=2,
        max_generations=12,
    )

    assert plan.profiles == ("base_quality_20", "lightx_er_sde_4", "lightx_sa_solver_4")
    assert plan.megapixels == (0.4, 1.0)
    assert plan.generation_count == 12
    assert [item.repeat for item in plan.variants] == [1] * 6 + [2] * 6


def test_matrix_guard_rejects_accidental_large_run_before_execution() -> None:
    try:
        build_matrix_plan(
            "base_quality_20, lightx_er_sde_4, lightx_sa_solver_4",
            "0.4, 1.0, 2.0",
            "base_quality_20",
            repeats=2,
            max_generations=12,
        )
    except ValueError as exc:
        assert "18 generations" in str(exc)
        assert "guard" in str(exc)
    else:
        raise AssertionError("large benchmark matrix was not guarded")


def test_matrix_pdd_requires_references_and_ref2va_context() -> None:
    for reference_count, selected_route, expected in (
        (0, "ref2va", "reference image"),
        (1, "fl2va", "REF2VA Director context"),
    ):
        try:
            build_matrix_plan(
                "base_quality_20, pdd_ref2va_4_900",
                "1.0",
                "base_quality_20",
                reference_count=reference_count,
                selected_route=selected_route,
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("invalid PDD matrix was not rejected")


def test_matrix_parsers_accept_labels_ids_mp_suffixes_and_remove_duplicates() -> None:
    assert parse_profile_list(
        "Base Quality - RES 20\nbase_quality_20\nLightX v0.1 - ER-SDE 4", "base_quality_20"
    ) == ("base_quality_20", "lightx_er_sde_4")
    assert parse_megapixel_list("0.4 MP, 1 megapixel, 1.0") == (0.4, 1.0)


def test_lazy_switch_validates_only_the_selected_connected_branch() -> None:
    inputs = H3StudioLazyImageSwitch.INPUT_TYPES()
    assert set(inputs["required"]) == {"benchmark_enabled"}
    assert inputs["optional"]["normal_image"][1]["lazy"] is True
    assert inputs["optional"]["benchmark_image"][1]["lazy"] is True

    switch = H3StudioLazyImageSwitch()
    assert switch.check_lazy_status(False) == ["normal_image"]
    assert switch.check_lazy_status(True) == ["benchmark_image"]
