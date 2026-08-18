"""Optional acceleration backends that remain owned by their upstream packages.

The Mamad8 PDD implementation is GPL-3.0 and intentionally is not copied into
H3 Studio. This module is a small interoperability layer: it discovers optional
external acceleration artifacts, resolves them deterministically, and invokes
the public ComfyUI execution surface without bundling upstream implementations.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

LIGHTX_MODEL_REPOSITORY = "https://huggingface.co/Kijai/MiniMax-H3_comfy"
LIGHTX_LORA_FILENAME = "minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors"
LIGHTX_V1_FL2V_4_PRUNED_FILENAME = "minimax_h3_fl2v_lightx2v_turbo_4step_v1.0_768p_resized_avg_rank_31_bf16.safetensors"
LIGHTX_V1_FL2V_8_PRUNED_FILENAME = "minimax_h3_fl2v_lightx2v_turbo_8step_v1.0_resized_avg_rank_24_bf16.safetensors"
LIGHTX_V01_REF2V_4_PRUNED_FILENAME = "minimax_h3_ref2v_lightx2v_turbo_4step_v0.1_resized_avg_rank_20_bf16.safetensors"
LIGHTX_V1_MODEL_REPOSITORY = "https://huggingface.co/lightx2v/Minimax-h3-Turbo"
LIGHTX_V1_LORA_FILENAME = "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"

PDD_REPOSITORY = "https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8"
PDD_MODEL_REPOSITORY = "https://huggingface.co/Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8"
PDD_NODE_IDS = (
    "MiniMaxH3PDDHeadsLoader",
    "MiniMaxH3PDDModelPatch",
    "MiniMaxH3PDDScheduler",
)


class PDDBackendError(ValueError):
    """Actionable configuration error for an optional acceleration backend."""


@dataclass(frozen=True, slots=True)
class LightXProfile:
    """One exact LightX adapter plus the ComfyUI recipe paired with it."""

    key: str
    sampler: str
    lora_filename: str
    repository: str
    artifact_tokens: tuple[str, ...]
    lora_strength: float
    recipe_source: str
    adapter_label: str
    route: str = "fl2va"
    runtime_profile: str | None = None
    scheduler: str = "simple"
    steps: int = 4
    shift_video: float = 12.0
    shift_audio: float = 3.0


_OLD_LIGHTX_TOKENS = ("minimax", "h3", "fl2v", "lightx2v", "4step", "v0.1", "resized", "rank", "21", "bf16")

LIGHTX_PROFILES: Mapping[str, LightXProfile] = {
    "lightx_v1_fl2v_8": LightXProfile(
        key="lightx_v1_fl2v_8",
        route="fl2va",
        sampler="euler",
        scheduler="simple",
        steps=8,
        shift_video=6.0,
        shift_audio=3.0,
        lora_filename=LIGHTX_V1_LORA_FILENAME,
        repository=LIGHTX_V1_MODEL_REPOSITORY,
        artifact_tokens=("minimax", "h3", "fl2v", "turbo", "8step", "v1.0", "comfyui", "bf16"),
        lora_strength=1.0,
        recipe_source="LightX2V v1.0 DMD family; official 8-step ComfyUI artifact",
        adapter_label="LightX v1.0 FL2VA 8-step · official full",
    ),
    "lightx_v1_fl2v_8_pruned": LightXProfile(
        key="lightx_v1_fl2v_8_pruned",
        route="fl2va",
        sampler="euler",
        scheduler="simple",
        steps=8,
        shift_video=6.0,
        shift_audio=3.0,
        lora_filename=LIGHTX_V1_FL2V_8_PRUNED_FILENAME,
        repository=LIGHTX_MODEL_REPOSITORY,
        artifact_tokens=("minimax", "h3", "fl2v", "lightx2v", "turbo", "8step", "v1.0", "resized", "rank", "24", "bf16"),
        lora_strength=1.0,
        recipe_source="LightX2V v1.0 8-step recipe; Kijai rank-reduced equivalent",
        adapter_label="LightX v1.0 FL2VA 8-step · Kijai pruned rank-24",
    ),
    "lightx_v1_fl2v_4_pruned": LightXProfile(
        key="lightx_v1_fl2v_4_pruned",
        route="fl2va",
        sampler="euler",
        scheduler="simple",
        steps=4,
        shift_video=6.0,
        shift_audio=3.0,
        lora_filename=LIGHTX_V1_FL2V_4_PRUNED_FILENAME,
        repository=LIGHTX_MODEL_REPOSITORY,
        artifact_tokens=("minimax", "h3", "fl2v", "lightx2v", "turbo", "4step", "v1.0", "768p", "resized", "rank", "31", "bf16"),
        lora_strength=1.0,
        recipe_source="LightX2V v1.0 768p DMD 4-step recipe; Kijai rank-reduced equivalent",
        adapter_label="LightX v1.0 FL2VA 4-step 768p · Kijai pruned rank-31",
    ),
    "lightx_er_sde_4": LightXProfile(
        key="lightx_er_sde_4",
        route="fl2va",
        runtime_profile="LightX v0.1 | ER-SDE 4 steps",
        sampler="er_sde",
        lora_filename=LIGHTX_LORA_FILENAME,
        repository=LIGHTX_MODEL_REPOSITORY,
        artifact_tokens=_OLD_LIGHTX_TOKENS,
        lora_strength=0.75,
        recipe_source="Kijai empirical ComfyUI",
        adapter_label="LightX v0.1 FL2VA resized rank-21",
    ),
    "lightx_sa_solver_4": LightXProfile(
        key="lightx_sa_solver_4",
        route="fl2va",
        runtime_profile="LightX v0.1 | SA-Solver 4 steps",
        sampler="sa_solver",
        lora_filename=LIGHTX_LORA_FILENAME,
        repository=LIGHTX_MODEL_REPOSITORY,
        artifact_tokens=_OLD_LIGHTX_TOKENS,
        lora_strength=0.75,
        recipe_source="Kijai empirical ComfyUI",
        adapter_label="LightX v0.1 FL2VA resized rank-21",
    ),
    "lightx_v01_ref2v_er_sde_4_pruned": LightXProfile(
        key="lightx_v01_ref2v_er_sde_4_pruned",
        route="ref2va",
        runtime_profile="LightX v0.1 | ER-SDE 4 steps",
        sampler="er_sde",
        lora_filename=LIGHTX_V01_REF2V_4_PRUNED_FILENAME,
        repository=LIGHTX_MODEL_REPOSITORY,
        artifact_tokens=("minimax", "h3", "ref2v", "lightx2v", "turbo", "4step", "v0.1", "resized", "rank", "20", "bf16"),
        lora_strength=0.75,
        recipe_source="Kijai v0.1 ComfyUI recipe applied to the rank-reduced REF2V adapter",
        adapter_label="LightX v0.1 REF2VA 4-step · Kijai pruned rank-20",
    ),
    "lightx_v01_ref2v_sa_solver_4_pruned": LightXProfile(
        key="lightx_v01_ref2v_sa_solver_4_pruned",
        route="ref2va",
        runtime_profile="LightX v0.1 | SA-Solver 4 steps",
        sampler="sa_solver",
        lora_filename=LIGHTX_V01_REF2V_4_PRUNED_FILENAME,
        repository=LIGHTX_MODEL_REPOSITORY,
        artifact_tokens=("minimax", "h3", "ref2v", "lightx2v", "turbo", "4step", "v0.1", "resized", "rank", "20", "bf16"),
        lora_strength=0.75,
        recipe_source="Kijai v0.1 ComfyUI recipe applied to the rank-reduced REF2V adapter",
        adapter_label="LightX v0.1 REF2VA 4-step · Kijai pruned rank-20",
    ),
}


@dataclass(frozen=True, slots=True)
class PDDProfile:
    key: str
    label: str
    training_step: int
    lora_filename: str
    heads_filename: str
    lora_strength: float = 2.0
    head_strength: float = 1.0
    blocks: int = 4

    @property
    def tokens(self) -> tuple[str, ...]:
        return ("h3", "pdd", f"step{self.training_step}")


PDD_PROFILES: Mapping[str, PDDProfile] = {
    "pdd_ref2va_4_600": PDDProfile(
        key="pdd_ref2va_4_600",
        label="Mamad8 PDD REF2VA · 4-step · ckpt 600",
        training_step=600,
        lora_filename="LORA_h3_pdd_af384_step600_s.safetensors",
        heads_filename="HEADS_h3_pdd_af384_step600_bank.safetensors",
    ),
    "pdd_ref2va_4_900": PDDProfile(
        key="pdd_ref2va_4_900",
        label="Mamad8 PDD REF2VA · 4-step · ckpt 900",
        training_step=900,
        lora_filename="LORA_h3_pdd_af384_step900_s.safetensors",
        heads_filename="HEADS_h3_pdd_af384_step900_bank.safetensors",
    ),
}


def is_pdd_profile(profile: str) -> bool:
    return str(profile or "") in PDD_PROFILES


def route_for_profile(profile: str, requested_route: str, reference_count: int) -> str:
    """Make Auto select PDD's trained REF2VA route when references exist."""

    if is_pdd_profile(profile) and requested_route == "auto" and reference_count > 0:
        return "ref2va"
    return requested_route


def _basename(value: str) -> str:
    return PurePosixPath(str(value or "").replace("\\", "/")).name.lower()


def resolve_artifact(
    filenames: Iterable[str],
    *,
    expected: str,
    tokens: Iterable[str],
    kind: str,
    repository: str = PDD_MODEL_REPOSITORY,
) -> str:
    """Resolve one artifact deterministically, rejecting ambiguous fallbacks."""

    values = sorted({str(value) for value in filenames if str(value).strip()}, key=str.lower)
    expected_name = expected.lower()
    exact = [value for value in values if _basename(value) == expected_name]
    if len(exact) == 1:
        return exact[0]
    required = tuple(str(token).lower() for token in tokens)
    candidates = [value for value in values if all(token in _basename(value) for token in required)]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        listed = ", ".join(candidates[:5])
        raise PDDBackendError(
            f"Several possible {kind} artifacts matched ({listed}). Keep the official filename {expected!r} "
            "or remove the ambiguous duplicates."
        )
    raise PDDBackendError(f"Missing {kind} artifact {expected!r}. Download the matching checkpoint from {repository}.")


def registered_pdd_nodes(node_mappings: Mapping[str, Any]) -> dict[str, Any]:
    missing = [node_id for node_id in PDD_NODE_IDS if node_id not in node_mappings]
    if missing:
        raise PDDBackendError(
            "Mamad8 PDD is selected but its custom node package is not available. Install or update "
            f"{PDD_REPOSITORY}, restart ComfyUI, and confirm these nodes load: {', '.join(missing)}."
        )
    return {node_id: node_mappings[node_id] for node_id in PDD_NODE_IDS}


def _first_output(result: Any, *, node_name: str) -> Any:
    if hasattr(result, "args"):
        values = result.args
    elif isinstance(result, dict) and "result" in result:
        values = result["result"]
    elif isinstance(result, (tuple, list)):
        values = result
    else:
        values = (result,)
    if not values:
        raise PDDBackendError(f"{node_name} returned no output. Update the Mamad8 PDD custom node package.")
    return values[0]


def _existing_bypass_injections(model: Any) -> tuple[Any, ...]:
    getter = getattr(model, "get_injections", None)
    if not callable(getter):
        return ()
    try:
        return tuple(getter("bypass_lora") or ())
    except Exception:
        return ()


def _flatten_bypass_injections(injections: tuple[Any, ...]) -> tuple[Any, ...]:
    """Flatten Studio composites while preserving adapter injection order."""

    flattened: list[Any] = []
    for injection in injections:
        children = getattr(injection, "_h3studio_bypass_children", None)
        if children:
            flattened.extend(_flatten_bypass_injections(tuple(children)))
        else:
            flattened.append(injection)

    unique: list[Any] = []
    seen: set[int] = set()
    for injection in flattened:
        identity = id(injection)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(injection)
    return tuple(unique)


def _composite_bypass_injection(injections: tuple[Any, ...]) -> tuple[Any, tuple[Any, ...]]:
    """Wrap nested bypass injections so teardown happens in strict LIFO order.

    Bypass LoRAs replace ``module.forward`` and remember the previous callable.
    When several adapters touch the same module they therefore form a wrapper
    stack. ComfyUI currently ejects top-level PatcherInjection objects in the
    same order it injected them, which is unsafe for a wrapper stack. One
    composite injection lets H3 Studio keep Comfy's public API while reversing
    teardown internally: A -> B -> C is always ejected C -> B -> A.
    """

    children = _flatten_bypass_injections(injections)

    try:
        from comfy.patcher_extension import PatcherInjection
    except Exception:  # pragma: no cover - pure tests run without ComfyUI
        class PatcherInjection:  # type: ignore[no-redef]
            def __init__(self, inject, eject):
                self.inject = inject
                self.eject = eject

    def inject_all(model_patcher):
        injected: list[Any] = []
        try:
            for injection in children:
                injection.inject(model_patcher)
                injected.append(injection)
        except Exception:
            # Do not leave half of a forward-wrapper chain attached when one
            # child fails to inject.
            for injection in reversed(injected):
                try:
                    injection.eject(model_patcher)
                except Exception:
                    continue
            raise

    def eject_all(model_patcher):
        first_error: Exception | None = None
        for injection in reversed(children):
            try:
                injection.eject(model_patcher)
            except Exception as exc:
                # Continue unwinding the remaining wrappers before surfacing
                # the first failure; otherwise the shared model stays poisoned.
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    composite = PatcherInjection(inject=inject_all, eject=eject_all)
    setattr(composite, "_h3studio_bypass_children", children)
    return composite, children


def _restore_stacked_bypass_injections(model: Any, previous: tuple[Any, ...]) -> int:
    """Preserve bypass LoRA stacks without creating recursive forward hooks.

    ComfyUI's public bypass loader stores each call under the fixed
    ``bypass_lora`` injection key, so a later LoRA replaces the earlier key.
    H3 Studio must preserve both adapter sets, but keeping them as separate
    top-level injections is unsafe: Comfy injects and ejects that list in the
    same order, while nested forward wrappers must unwind in reverse order.

    Collapse the full stack into one composite PatcherInjection. It injects
    children in order and ejects them in strict reverse order, preventing a
    BypassForwardHook from ever retaining its own ``_bypass_forward`` as the
    original forward across repeated generations.
    """

    if not previous:
        return 0
    getter = getattr(model, "get_injections", None)
    setter = getattr(model, "set_injections", None)
    if not callable(getter) or not callable(setter):
        return 0
    try:
        current = tuple(getter("bypass_lora") or ())
        if not current:
            return 0
        composite, children = _composite_bypass_injection((*previous, *current))
        if len(children) <= 1:
            setter("bypass_lora", list(children))
        else:
            setter("bypass_lora", [composite])
        return len(children)
    except Exception:
        return 0


def _load_model_lora(
    model: Any,
    lora_name: str,
    strength: float,
    node_mappings: Mapping[str, Any],
) -> tuple[Any, str]:
    """Load an adapter without eagerly materializing quantized H3 weights.

    Current ComfyUI exposes a bypass adapter path which performs the LoRA
    contribution during each layer's forward pass. This avoids the very slow
    merge -> requantize cycle seen with INT8/FP8 H3 checkpoints. Existing bypass
    injections are preserved as one LIFO-safe composite so multiple user LoRAs
    can be stacked on LightX without poisoning repeated generation cycles.
    Older ComfyUI builds retain the normal node-loader fallback for compatibility.
    """

    try:
        import comfy.sd
        import comfy.utils
        import folder_paths

        bypass_loader = getattr(comfy.sd, "load_bypass_lora_for_models", None)
        if bypass_loader is not None:
            path = folder_paths.get_full_path_or_raise("loras", lora_name)
            weights = comfy.utils.load_torch_file(path, safe_load=True)
            previous = _existing_bypass_injections(model)
            patched, _clip = bypass_loader(model, None, weights, float(strength), 0.0)
            combined = _restore_stacked_bypass_injections(patched, previous)
            backend = "bypass-forward-stacked" if combined else "bypass-forward"
            return patched, backend
    except Exception as exc:
        # Keep an actionable fallback on older ComfyUI rather than making every
        # acceleration profile unavailable. The caller prints the backend so
        # users can see whether the fast path was active.
        import logging

        logging.getLogger(__name__).warning(
            "[H3 Studio] Bypass LoRA unavailable for %s (%s); using legacy weight patches. Update ComfyUI for fast quantized adapter loading.",
            lora_name,
            exc,
        )

    loader_class = node_mappings.get("LoraLoaderModelOnly")
    if loader_class is not None:
        loader = loader_class()
        result = loader.load_lora_model_only(model, lora_name, float(strength))
        return _first_output(result, node_name="ComfyUI LoRA Loader (model only)"), "legacy-weight-patch"

    loader_class = node_mappings.get("LoraLoader")
    if loader_class is None:
        raise PDDBackendError("ComfyUI's LoRA Loader is unavailable; update ComfyUI before using accelerated H3 profiles.")
    loader = loader_class()
    result = loader.load_lora(model, None, lora_name, float(strength), 0.0)
    return _first_output(result, node_name="ComfyUI LoRA Loader"), "legacy-weight-patch"


def build_lightx_backend(model: Any, profile_key: str):
    """Apply the exact LightX adapter and the sampling recipe paired with it."""

    if profile_key not in LIGHTX_PROFILES:
        raise PDDBackendError(f"Unknown LightX profile: {profile_key}")
    profile = LIGHTX_PROFILES[profile_key]

    import folder_paths
    import nodes

    choices = folder_paths.get_filename_list("loras")
    lora_name = resolve_artifact(
        choices,
        expected=profile.lora_filename,
        tokens=profile.artifact_tokens,
        kind=f"{profile.adapter_label} LoRA",
        repository=profile.repository,
    )
    patched_model, patch_backend = _load_model_lora(
        model,
        lora_name,
        profile.lora_strength,
        getattr(nodes, "NODE_CLASS_MAPPINGS", {}),
    )

    if profile.runtime_profile:
        from .nodes.image_runtime import H3StudioSamplingPreset

        built_model, sampler, sigmas, base_info = H3StudioSamplingPreset().build(
            patched_model,
            profile.runtime_profile,
        )
    else:
        # LightX2V's v1.0 H3 DMD family uses guidance-free Euler updates with
        # video/audio flow shifts 6/3. Keep each artifact's trained step count
        # explicit so full and rank-reduced variants resolve to the same recipe.
        from .nodes.image_runtime import H3StudioSamplingSettings

        built_model, sampler, sigmas, base_info = H3StudioSamplingSettings().build(
            model=patched_model,
            sampler_name=profile.sampler,
            scheduler=profile.scheduler,
            steps=profile.steps,
            denoise=1.0,
            shift_video=profile.shift_video,
            shift_audio=profile.shift_audio,
            beta_alpha=0.6,
            beta_beta=0.6,
        )

    info = (
        f"profile={profile.key} | route={profile.route.upper()} | {base_info} | adapter={profile.adapter_label} | "
        f"lora={lora_name} @ {profile.lora_strength:g} | recipe={profile.recipe_source} | "
        f"lora_backend={patch_backend}"
    )
    return built_model, sampler, sigmas, info


def build_pdd_backend(model: Any, profile_key: str, *, selected_route: str, reference_count: int):
    """Build the trained Mamad8 four-step path through its registered nodes."""

    if profile_key not in PDD_PROFILES:
        raise PDDBackendError(f"Unknown Mamad8 PDD profile: {profile_key}")
    if selected_route != "ref2va" or reference_count < 1:
        raise PDDBackendError(
            "Mamad8 PDD was trained for REF2VA reference generation. Add at least one reference and use Auto/REF2VA, "
            "or choose a Base/LightX profile for this request."
        )

    # Deferred imports keep pure state/prompt tests runnable outside ComfyUI.
    import comfy.samplers
    import folder_paths
    import nodes

    mappings = getattr(nodes, "NODE_CLASS_MAPPINGS", {})
    pdd_nodes = registered_pdd_nodes(mappings)
    profile = PDD_PROFILES[profile_key]

    lora_choices = folder_paths.get_filename_list("loras")
    heads_choices = folder_paths.get_filename_list("pdd_heads")
    lora_name = resolve_artifact(
        lora_choices,
        expected=profile.lora_filename,
        tokens=(*profile.tokens, "lora"),
        kind="PDD student LoRA",
    )
    heads_name = resolve_artifact(
        heads_choices,
        expected=profile.heads_filename,
        tokens=(*profile.tokens, "heads"),
        kind="PDD heads bank",
    )

    lora_model, patch_backend = _load_model_lora(model, lora_name, profile.lora_strength, mappings)

    # Apply H3's trained 12/3 AV shift before the external patch so Mamad8's
    # enforce contract can validate the live model path rather than guessing.
    from .nodes.image_runtime import H3StudioSamplingSettings

    shifted_model, sampling_backend = H3StudioSamplingSettings._apply_h3_shift(lora_model, 12.0, 3.0)
    heads = _first_output(
        pdd_nodes["MiniMaxH3PDDHeadsLoader"].execute(heads_name, blocks=profile.blocks, partition=""),
        node_name="MiniMax H3 PDD Heads Loader",
    )
    patched_model = _first_output(
        pdd_nodes["MiniMaxH3PDDModelPatch"].execute(
            shifted_model,
            heads,
            mode="exact_euler_step",
            on_out_of_grid="clamp",
            head_strength=profile.head_strength,
            contract="enforce",
        ),
        node_name="MiniMax H3 PDD Model Patch",
    )
    sigmas = _first_output(
        pdd_nodes["MiniMaxH3PDDScheduler"].execute(
            heads,
            mode="trained_blocks",
            steps=profile.blocks,
            denoise=1.0,
        ),
        node_name="MiniMax H3 PDD Scheduler",
    )
    sampler = comfy.samplers.sampler_object("euler")
    info = (
        f"profile={profile.key} | backend=Mamad8 PDD external | checkpoint={profile.training_step} | "
        f"sampler=euler | scheduler=trained_blocks | steps={profile.blocks} | denoise=1 | "
        f"shift_video=12 | shift_audio=3 | lora={lora_name} @ {profile.lora_strength:g} | "
        f"lora_backend={patch_backend} | heads={heads_name} @ {profile.head_strength:g} | "
        f"contract=enforce | sampling_backend={sampling_backend}"
    )
    return patched_model, sampler, sigmas, info
