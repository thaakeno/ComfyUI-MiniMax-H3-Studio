from __future__ import annotations

import importlib
import sys
from types import ModuleType

import pytest


@pytest.fixture(autouse=True)
def _discard_stubbed_loader():
    yield
    sys.modules.pop("h3studio.nodes.loader", None)


def _load_with_models(monkeypatch, filenames):
    folder_paths = ModuleType("folder_paths")
    folder_paths.get_filename_list = lambda category: list(filenames) if category in {"text_encoders", "clip"} else []
    nodes = ModuleType("nodes")
    nodes.NODE_CLASS_MAPPINGS = {}
    comfy = ModuleType("comfy")
    comfy.__path__ = []
    model_management = ModuleType("comfy.model_management")
    comfy.model_management = model_management
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths)
    monkeypatch.setitem(sys.modules, "nodes", nodes)
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.model_management", model_management)
    sys.modules.pop("h3studio.nodes.loader", None)
    return importlib.import_module("h3studio.nodes.loader")


def test_nvfp4_is_preferred_and_legacy_default_migrates(monkeypatch) -> None:
    nvfp4 = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
    int8 = "qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
    loader = _load_with_models(monkeypatch, [int8, nvfp4])
    assert loader.clip_choices() == [nvfp4, int8]
    assert loader._resolve_text_encoder(int8) == nvfp4


def test_deliberately_named_int8_choice_is_respected(monkeypatch) -> None:
    nvfp4 = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
    explicit = "custom_qwen3vl_32b_minimax_h3_int8_convrot_v2.safetensors"
    loader = _load_with_models(monkeypatch, [explicit, nvfp4])
    assert loader._resolve_text_encoder(explicit) == explicit


def test_legacy_separate_prompt_writer_cannot_stage_a_second_model(monkeypatch) -> None:
    loader = _load_with_models(
        monkeypatch,
        ["qwen3vl_4b_fp8_scaled.safetensors", "qwen3vl_8b_fp8_scaled.safetensors"],
    )
    assert loader.prompt_writer_choices() == [loader.FAST_WRITER]
    assert loader._resolve_prompt_writer("qwen3vl_8b_fp8_scaled.safetensors", "qwen3vl_4b_fp8_scaled.safetensors") is None
