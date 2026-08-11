"""Pure benchmark planning helpers shared by the ComfyUI runtime and tests."""

from __future__ import annotations

from dataclasses import dataclass

AB_MEGAPIXELS = (0.40, 1.00, 2.00)
PROFILE_CHOICES = {
    "Director selected profile": "director",
    "Base Quality - RES 20": "base_quality_20",
    "Base Balanced - RES 12": "base_balanced_12",
    "LightX v0.1 - ER-SDE 4": "lightx_er_sde_4",
    "LightX v0.1 - SA-Solver 4": "lightx_sa_solver_4",
    "PDD REF2VA - 4-step - ckpt 600": "pdd_ref2va_4_600",
    "PDD REF2VA - 4-step - ckpt 900": "pdd_ref2va_4_900",
}
DEFAULT_MATRIX_PROFILES = ("base_quality_20", "lightx_er_sde_4")
DEFAULT_MATRIX_MEGAPIXELS = AB_MEGAPIXELS
MAX_MATRIX_GENERATIONS = 128

# Backward-compatible exports for workflows from alpha.10 and earlier.
BASELINE_PROFILES = {key: value for key, value in PROFILE_CHOICES.items() if value.startswith("base_")}
ACCELERATOR_PROFILES = {
    key: value for key, value in PROFILE_CHOICES.items() if value == "director" or not value.startswith("base_")
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
    repeat: int = 1


@dataclass(frozen=True, slots=True)
class BenchmarkMatrixPlan:
    profiles: tuple[str, ...]
    megapixels: tuple[float, ...]
    repeats: int
    variants: tuple[ABVariantSpec, ...]

    @property
    def generation_count(self) -> int:
        return len(self.variants)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in str(value).replace("\r", "\n").replace(",", "\n").split("\n") if part.strip())


def parse_profile_list(value: str, director_profile: str) -> tuple[str, ...]:
    """Parse labels or stable profile IDs while preserving the user's order."""

    requested = _tokens(value)
    if not requested:
        raise ValueError("Select at least one benchmark profile.")
    profiles = tuple(dict.fromkeys(resolve_profile(item, director_profile) for item in requested))
    if not profiles:
        raise ValueError("Select at least one benchmark profile.")
    return profiles


def parse_megapixel_list(value: str) -> tuple[float, ...]:
    """Parse a comma/newline separated resolution list with H3 Studio's direct limits."""

    requested = _tokens(value)
    if not requested:
        raise ValueError("Enter at least one benchmark resolution in megapixels.")
    values: list[float] = []
    for item in requested:
        cleaned = item.lower().replace("megapixels", "").replace("megapixel", "").replace("mp", "").strip()
        try:
            megapixels = float(cleaned)
        except ValueError as exc:
            raise ValueError(f"Invalid benchmark resolution {item!r}; use values such as 0.4, 1.0, 2.0.") from exc
        if not 0.20 <= megapixels <= 8.50:
            raise ValueError(f"Benchmark resolution {megapixels:g} MP is outside H3 Studio's 0.20-8.50 MP range.")
        if megapixels not in values:
            values.append(megapixels)
    return tuple(values)


def _seed_for_cell(base_seed: int, strategy: str, seed_step: int, row: int, cell: int) -> int:
    if strategy == SEED_STRATEGIES[0]:
        offset = 0
    elif strategy == SEED_STRATEGIES[1]:
        offset = row
    elif strategy == SEED_STRATEGIES[2]:
        offset = cell
    else:
        raise ValueError(f"Unknown benchmark seed strategy: {strategy}")
    return (base_seed + offset * seed_step) % (2**63)


def build_matrix_plan(
    profiles: str,
    megapixels: str,
    director_profile: str,
    *,
    base_seed: int = 0,
    seed_strategy: str = SEED_STRATEGIES[0],
    seed_step: int = 1,
    repeats: int = 1,
    max_generations: int = 24,
    allow_large_matrix: bool = False,
    reference_count: int = 0,
    selected_route: str = "fl2va",
) -> BenchmarkMatrixPlan:
    """Build and validate an extensible profile x resolution x repeat matrix."""

    resolved_profiles = parse_profile_list(profiles, director_profile)
    resolved_megapixels = parse_megapixel_list(megapixels)
    repeats = max(1, min(16, int(repeats)))
    seed_step = max(1, min(1_000_000, int(seed_step)))
    base_seed = max(0, min(2**63 - 1, int(base_seed)))
    generation_count = len(resolved_profiles) * len(resolved_megapixels) * repeats
    if generation_count > MAX_MATRIX_GENERATIONS:
        raise ValueError(
            f"This benchmark requests {generation_count} generations; the hard safety limit is "
            f"{MAX_MATRIX_GENERATIONS}. Reduce profiles, resolutions, or repeats."
        )
    guard = max(1, min(MAX_MATRIX_GENERATIONS, int(max_generations)))
    if generation_count > guard and not bool(allow_large_matrix):
        raise ValueError(
            f"This benchmark will run {generation_count} generations, above your {guard}-generation guard. "
            "Reduce the matrix or enable 'allow large matrix' after checking the count."
        )
    if any(profile.startswith("pdd_ref2va_") for profile in resolved_profiles):
        if reference_count < 1:
            raise ValueError("PDD benchmark profiles require at least one reference image; no generation was started.")
        if selected_route != "ref2va":
            raise ValueError(
                "PDD benchmark profiles require a REF2VA Director context. Select a PDD profile with Auto route "
                "in the Director, or force REF2VA, then rebuild the context."
            )

    variants: list[ABVariantSpec] = []
    cell = 0
    for repeat in range(1, repeats + 1):
        for resolution_index, requested_mp in enumerate(resolved_megapixels):
            row = (repeat - 1) * len(resolved_megapixels) + resolution_index
            for profile in resolved_profiles:
                variants.append(
                    ABVariantSpec(
                        requested_megapixels=requested_mp,
                        profile=profile,
                        accelerated=not profile.startswith("base_"),
                        seed=_seed_for_cell(base_seed, seed_strategy, seed_step, row, cell),
                        repeat=repeat,
                    )
                )
                cell += 1
    return BenchmarkMatrixPlan(resolved_profiles, resolved_megapixels, repeats, tuple(variants))


def build_seed_plan(base_seed: int, strategy: str, step: int = 1) -> tuple[int, ...]:
    """Backward-compatible six-cell A/B seed plan."""

    return tuple(_seed_for_cell(max(0, min(2**63 - 1, int(base_seed))), strategy, max(1, int(step)), row, cell)
                 for cell, row in enumerate((0, 0, 1, 1, 2, 2)))


def resolve_profile(choice: str, director_profile: str) -> str:
    """Resolve a benchmark profile without making Base an invalid state."""

    aliases = {"Director selected accelerator": "director"}
    selected = PROFILE_CHOICES.get(str(choice), aliases.get(str(choice), str(choice)))
    if selected == "director":
        selected = str(director_profile)
    known = set(PROFILE_CHOICES.values()) - {"director"}
    if selected not in known:
        raise ValueError(f"Unknown H3 benchmark profile: {selected}")
    return selected


def resolve_accelerator(choice: str, director_profile: str) -> str:
    """Compatibility alias; unlike alpha.10, a Director Base profile is valid."""

    return resolve_profile(choice, director_profile)


def build_ab_variants(
    profile_a_choice: str,
    profile_b_choice: str,
    director_profile: str,
    base_seed: int = 0,
    seed_strategy: str = SEED_STRATEGIES[0],
    seed_step: int = 1,
) -> tuple[ABVariantSpec, ...]:
    """Backward-compatible two-profile, three-resolution matrix."""

    profile_a = resolve_profile(profile_a_choice, director_profile)
    profile_b = resolve_profile(profile_b_choice, director_profile)
    return build_matrix_plan(
        f"{profile_a},{profile_b}",
        ",".join(str(value) for value in AB_MEGAPIXELS),
        director_profile,
        base_seed=base_seed,
        seed_strategy=seed_strategy,
        seed_step=seed_step,
        max_generations=6,
        allow_large_matrix=True,
        reference_count=1 if profile_a.startswith("pdd_") or profile_b.startswith("pdd_") else 0,
        selected_route="ref2va" if profile_a.startswith("pdd_") or profile_b.startswith("pdd_") else "fl2va",
    ).variants


def short_profile_label(profile: str, accelerated: bool | None = None) -> str:
    labels = {
        "base_quality_20": "No LoRA - Base RES20",
        "base_balanced_12": "No LoRA - Base RES12",
        "lightx_er_sde_4": "LoRA - LightX ER-SDE 4",
        "lightx_sa_solver_4": "LoRA - LightX SA-Solver 4",
        "pdd_ref2va_4_600": "LoRA - PDD REF2VA 4 - ckpt 600",
        "pdd_ref2va_4_900": "LoRA - PDD REF2VA 4 - ckpt 900",
    }
    if accelerated is None:
        accelerated = not str(profile).startswith("base_")
    return labels.get(profile, f"{'LoRA' if accelerated else 'No LoRA'} - {profile}")
