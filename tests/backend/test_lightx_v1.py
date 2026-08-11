from __future__ import annotations

import sys
from types import ModuleType

import pytest

from h3studio.acceleration import LIGHTX_V1_LORA_FILENAME, build_lightx_backend
from h3studio.errors import RouteError
from h3studio.routing import validate_generation_contract


def test_lightx_v1_build_uses_eight_step_6_3_euler_recipe(monkeypatch) -> None:
    calls: list[tuple] = []

    class LoraLoader:
        def load_lora_model_only(self, model, name, strength):
            calls.append(("lora", model, name, strength))
            return ("lora-model",)

    class SamplingSettings:
        def build(self, **kwargs):
            calls.append(("sampling", kwargs))
            return "shifted-model", "sampler:euler", "sigmas", "sampling-info"

    folder_module = ModuleType("folder_paths")
    folder_module.get_filename_list = lambda category: [LIGHTX_V1_LORA_FILENAME]
    nodes_module = ModuleType("nodes")
    nodes_module.NODE_CLASS_MAPPINGS = {"LoraLoaderModelOnly": LoraLoader}
    runtime_module = ModuleType("h3studio.nodes.image_runtime")
    runtime_module.H3StudioSamplingSettings = SamplingSettings

    # Make the optional bypass import fail cleanly so this pure unit test uses
    # the ordinary Comfy model-only loader surface.
    monkeypatch.delitem(sys.modules, "comfy", raising=False)
    monkeypatch.setitem(sys.modules, "folder_paths", folder_module)
    monkeypatch.setitem(sys.modules, "nodes", nodes_module)
    monkeypatch.setitem(sys.modules, "h3studio.nodes.image_runtime", runtime_module)

    model, sampler, sigmas, info = build_lightx_backend("base-model", "lightx_v1_fl2v_8")

    assert model == "shifted-model"
    assert sampler == "sampler:euler"
    assert sigmas == "sigmas"
    assert calls[0] == ("lora", "base-model", LIGHTX_V1_LORA_FILENAME, 1.0)
    sampling = calls[1][1]
    assert sampling["sampler_name"] == "euler"
    assert sampling["scheduler"] == "simple"
    assert sampling["steps"] == 8
    assert sampling["denoise"] == 1.0
    assert sampling["shift_video"] == 6.0
    assert sampling["shift_audio"] == 3.0
    assert "LightX v1.0 FL2V 8-step" in info


def test_lightx_fl2v_rejects_reference_mix_before_model_work() -> None:
    with pytest.raises(RouteError, match="FL2V adapter"):
        validate_generation_contract("reference_edit", "auto", "lightx_v1_fl2v_8", 2)

    with pytest.raises(RouteError, match="FL2V/FL2VA-only"):
        validate_generation_contract("auto", "ref2va", "lightx_v1_fl2v_8", 1)


def test_lightx_v1_allows_t2i_and_single_source_fl2va() -> None:
    validate_generation_contract("text_to_image", "auto", "lightx_v1_fl2v_8", 0)
    validate_generation_contract("image_to_image", "auto", "lightx_v1_fl2v_8", 1)
