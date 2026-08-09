"""Pure A/B-matrix planning helpers shared by the ComfyUI runtime and tests."""

from __future__ import annotations

from dataclasses import dataclass

AB_MEGAPIXELS = (0.40, 1.00, 2.00)
BASELINE_PROFILES = {"Base Quality - RES 20": "base_quality_20", "Base Balanced - RES 12": "base_balanced_12"}
ACCELERATOR_PROFILES = {
    "Director selected accelerator": "director",
    "LightX v0.1 - ER-SDE 4": "lightx_er_sde_4",
    "LightX v0.1 - SA-Solver 4": "lightx_sa_solver_4",
    "PDD REF2VA - 4-step - ckpt 600": "pdd_ref2va_4_600",
    "PDD REF2VA - 4-step - ckpt 900": "pdd_ref2va_4_900",
}
SEED_STRATEGIES = (
    "Same seed for all - fair comparison",
    "New seed each row - paired comparison",
    "New seed every image - diversity sweep",
)


@dataclass(frozen=True, slots=True)
class ABVariantSpec:
    requested_megapixels: float
    profile: str
    accelerated: bool
    seed: int = 0


def build_seed_plan(base_seed: int, strategy: str, step: int = 1) -> tuple[int, ...]:
    """Assign six seeds while preserving explicit comparison semantics."""

    base_seed = max(0, min(2**63 - 1, int(base_seed)))
    step = max(1, min(1_000_000, int(step)))
    if strategy == SEED_STRATEGIES[0]:
        offsets = (0, 0, 0, 0, 0, 0)
    elif strategy == SEED_STRATEGIES[1]:
        offsets = (0, 0, 1, 1, 2, 2)
    elif strategy == SEED_STRATEGIES[2]:
        offsets = (0, 1, 2, 3, 4, 5)
    else:
        raise ValueError(f"Unknown A/B seed strategy: {strategy}")
    return tuple((base_seed + offset * step) % (2**63) for offset in offsets)


def resolve_accelerator(choice: str, director_profile: str) -> str:
    selected = ACCELERATOR_PROFILES.get(str(choice), str(choice))
    if selected == "director":
        selected = str(director_profile)
    if selected.startswith("base_"):
        raise ValueError(
            "The Director currently selects a no-LoRA Base profile. Choose LightX or PDD explicitly in the A/B node."
        )
    if selected not in set(ACCELERATOR_PROFILES.values()) - {"director"}:
        raise ValueError(f"Unknown A/B accelerator profile: {selected}")
    return selected


def build_ab_variants(
    baseline_choice: str,
    accelerator_choice: str,
    director_profile: str,
    base_seed: int = 0,
    seed_strategy: str = SEED_STRATEGIES[0],
    seed_step: int = 1,
) -> tuple[ABVariantSpec, ...]:
    baseline = BASELINE_PROFILES.get(str(baseline_choice), str(baseline_choice))
    if baseline not in BASELINE_PROFILES.values():
        raise ValueError(f"Unknown A/B baseline profile: {baseline}")
    accelerator = resolve_accelerator(accelerator_choice, director_profile)
    seeds = iter(build_seed_plan(base_seed, seed_strategy, seed_step))
    return tuple(
        ABVariantSpec(megapixels, profile, accelerated, next(seeds))
        for megapixels in AB_MEGAPIXELS
        for profile, accelerated in ((baseline, False), (accelerator, True))
    )


def short_profile_label(profile: str, accelerated: bool) -> str:
    labels = {
        "base_quality_20": "No LoRA - Base RES20",
        "base_balanced_12": "No LoRA - Base RES12",
        "lightx_er_sde_4": "LoRA - LightX ER-SDE 4",
        "lightx_sa_solver_4": "LoRA - LightX SA-Solver 4",
        "pdd_ref2va_4_600": "LoRA - PDD REF2VA 4 - ckpt 600",
        "pdd_ref2va_4_900": "LoRA - PDD REF2VA 4 - ckpt 900",
    }
    return labels.get(profile, f"{'LoRA' if accelerated else 'No LoRA'} - {profile}")
