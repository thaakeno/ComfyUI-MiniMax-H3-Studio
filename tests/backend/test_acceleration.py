from __future__ import annotations

import sys
from types import ModuleType

import pytest

from h3studio.acceleration import (
    PDD_PROFILES,
    PDDBackendError,
    build_pdd_backend,
    registered_pdd_nodes,
    resolve_artifact,
    route_for_profile,
)


def test_pdd_profiles_keep_checkpoint_artifacts_paired() -> None:
    for profile in PDD_PROFILES.values():
        token = f"step{profile.training_step}"
        assert token in profile.lora_filename.lower()
        assert token in profile.heads_filename.lower()
        assert profile.blocks == 4
        assert profile.lora_strength == 2.0
        assert profile.head_strength == 1.0


def test_artifact_resolution_prefers_official_filename_and_rejects_ambiguity() -> None:
    expected = "LORA_h3_pdd_af384_step900_s.safetensors"
    assert resolve_artifact(
        [f"nested/{expected}", "h3_pdd_step900_lora_copy.safetensors"],
        expected=expected,
        tokens=("h3", "pdd", "step900", "lora"),
        kind="student LoRA",
    ) == f"nested/{expected}"
    with pytest.raises(PDDBackendError, match="Several possible"):
        resolve_artifact(
            ["a/h3_pdd_step900_lora.safetensors", "b/h3_pdd_step900_lora.safetensors"],
            expected=expected,
            tokens=("h3", "pdd", "step900", "lora"),
            kind="student LoRA",
        )


def test_registered_pdd_nodes_fails_with_install_instructions() -> None:
    with pytest.raises(PDDBackendError, match="Install or update"):
        registered_pdd_nodes({})


def test_pdd_profile_routes_auto_reference_requests_to_ref2va() -> None:
    assert route_for_profile("pdd_ref2va_4_900", "auto", 1) == "ref2va"
    assert route_for_profile("pdd_ref2va_4_900", "auto", 0) == "auto"
    assert route_for_profile("pdd_ref2va_4_900", "fl2va", 3) == "fl2va"
    assert route_for_profile("base_quality_20", "auto", 3) == "auto"


def test_pdd_backend_orchestrates_external_nodes_without_copying_implementation(monkeypatch) -> None:
    calls: list[tuple] = []

    class Output:
        def __init__(self, value):
            self.args = (value,)

    class LoraLoader:
        def load_lora_model_only(self, model, name, strength):
            calls.append(("lora", model, name, strength))
            return ("lora-model",)

    class HeadsLoader:
        @classmethod
        def execute(cls, name, blocks=0, partition=""):
            calls.append(("heads", name, blocks, partition))
            return Output("heads")

    class ModelPatch:
        @classmethod
        def execute(cls, model, heads, **kwargs):
            calls.append(("patch", model, heads, kwargs))
            return Output("pdd-model")

    class Scheduler:
        @classmethod
        def execute(cls, heads, **kwargs):
            calls.append(("scheduler", heads, kwargs))
            return Output("pdd-sigmas")

    mappings = {
        "LoraLoaderModelOnly": LoraLoader,
        "MiniMaxH3PDDHeadsLoader": HeadsLoader,
        "MiniMaxH3PDDModelPatch": ModelPatch,
        "MiniMaxH3PDDScheduler": Scheduler,
    }
    nodes_module = ModuleType("nodes")
    nodes_module.NODE_CLASS_MAPPINGS = mappings
    folder_module = ModuleType("folder_paths")
    folder_module.get_filename_list = lambda category: {
        "loras": ["LORA_h3_pdd_af384_step900_s.safetensors"],
        "pdd_heads": ["HEADS_h3_pdd_af384_step900_bank.safetensors"],
    }[category]
    comfy_module = ModuleType("comfy")
    comfy_module.__path__ = []
    samplers_module = ModuleType("comfy.samplers")
    samplers_module.sampler_object = lambda name: f"sampler:{name}"
    comfy_module.samplers = samplers_module

    class SamplingSettings:
        @staticmethod
        def _apply_h3_shift(model, shift_video, shift_audio):
            calls.append(("shift", model, shift_video, shift_audio))
            return "shifted-model", "ModelSamplingAV"

    runtime_module = ModuleType("h3studio.nodes.image_runtime")
    runtime_module.H3StudioSamplingSettings = SamplingSettings
    monkeypatch.setitem(sys.modules, "nodes", nodes_module)
    monkeypatch.setitem(sys.modules, "folder_paths", folder_module)
    monkeypatch.setitem(sys.modules, "comfy", comfy_module)
    monkeypatch.setitem(sys.modules, "comfy.samplers", samplers_module)
    monkeypatch.setitem(sys.modules, "h3studio.nodes.image_runtime", runtime_module)

    model, sampler, sigmas, info = build_pdd_backend(
        "base-model",
        "pdd_ref2va_4_900",
        selected_route="ref2va",
        reference_count=2,
    )

    assert model == "pdd-model"
    assert sampler == "sampler:euler"
    assert sigmas == "pdd-sigmas"
    assert "checkpoint=900" in info
    assert [call[0] for call in calls] == ["lora", "shift", "heads", "patch", "scheduler"]
    assert calls[3][3] == {
        "mode": "exact_euler_step",
        "on_out_of_grid": "clamp",
        "head_strength": 1.0,
        "contract": "enforce",
    }


def test_pdd_backend_rejects_non_reference_route_before_importing_comfy() -> None:
    with pytest.raises(PDDBackendError, match="trained for REF2VA"):
        build_pdd_backend("model", "pdd_ref2va_4_900", selected_route="fl2va", reference_count=0)
