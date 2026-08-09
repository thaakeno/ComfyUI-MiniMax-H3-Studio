"""Optional acceleration backends that remain owned by their upstream packages.

The Mamad8 PDD implementation is GPL-3.0 and intentionally is not copied into
H3 Studio.  This module is a small interoperability layer: it discovers the
registered V3 nodes, resolves the matching local artifacts, and invokes their
public node execution surface when a PDD profile is selected.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

PDD_REPOSITORY = "https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8"
PDD_MODEL_REPOSITORY = "https://huggingface.co/Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8"
PDD_NODE_IDS = (
    "MiniMaxH3PDDHeadsLoader",
    "MiniMaxH3PDDModelPatch",
    "MiniMaxH3PDDScheduler",
)


class PDDBackendError(ValueError):
    """Actionable configuration error for the optional Mamad8 backend."""


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
    raise PDDBackendError(
        f"Missing {kind} artifact {expected!r}. Download the matching Mamad8 checkpoint from "
        f"{PDD_MODEL_REPOSITORY}."
    )


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


def _load_model_lora(model: Any, lora_name: str, strength: float, node_mappings: Mapping[str, Any]) -> Any:
    loader_class = node_mappings.get("LoraLoaderModelOnly")
    if loader_class is not None:
        loader = loader_class()
        result = loader.load_lora_model_only(model, lora_name, float(strength))
        return _first_output(result, node_name="ComfyUI LoRA Loader (model only)")

    loader_class = node_mappings.get("LoraLoader")
    if loader_class is None:
        raise PDDBackendError("ComfyUI's LoRA Loader is unavailable; update ComfyUI before using Mamad8 PDD.")
    loader = loader_class()
    result = loader.load_lora(model, None, lora_name, float(strength), 0.0)
    return _first_output(result, node_name="ComfyUI LoRA Loader")


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

    lora_model = _load_model_lora(model, lora_name, profile.lora_strength, mappings)

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
        f"heads={heads_name} @ {profile.head_strength:g} | contract=enforce | sampling_backend={sampling_backend}"
    )
    return patched_model, sampler, sigmas, info
