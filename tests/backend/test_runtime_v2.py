from __future__ import annotations

import sys
from types import ModuleType

from h3studio.runtime_v2 import release_stage


class FakePatcher:
    def __init__(self):
        self.loaded = 12 * 1024**3

    def loaded_size(self):
        return self.loaded


def test_runtime_v2_uses_targeted_comfy_manager_release(monkeypatch) -> None:
    comfy = ModuleType("comfy")
    comfy.__path__ = []
    manager = ModuleType("comfy.model_management")
    calls = []

    def unload_model_and_clones(patcher, *, unload_additional_models=False):
        calls.append((patcher, unload_additional_models))
        patcher.loaded = 0

    manager.unload_model_and_clones = unload_model_and_clones
    comfy.model_management = manager
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.model_management", manager)

    patcher = FakePatcher()
    result = release_stage(patcher, label="diffusion")

    assert calls == [(patcher, False)]
    assert result.mode == "released"
    assert result.before == 12 * 1024**3
    assert result.after == 0


def test_runtime_v2_release_is_nonfatal_when_manager_is_missing(monkeypatch) -> None:
    comfy = ModuleType("comfy")
    comfy.__path__ = []
    manager = ModuleType("comfy.model_management")
    comfy.model_management = manager
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.model_management", manager)

    result = release_stage(FakePatcher(), label="vae")
    assert result.mode == "manager-api-missing"
