from __future__ import annotations

import sys
from types import ModuleType

import h3studio.nodes.preview as preview_module
from h3studio.nodes.preview import H3StudioTAEH3Preview, _PreviewWrapper


def test_preview_wrapper_advances_executor_instead_of_recursing(monkeypatch) -> None:
    torch_module = ModuleType("torch")
    monkeypatch.setitem(sys.modules, "torch", torch_module)
    calls = []

    class Executor:
        def __call__(self, *args, **kwargs):
            calls.append((args, kwargs))
            return "next-wrapper"

        def execute(self, *args, **kwargs):
            raise AssertionError("execute() would repeat the current wrapper index")

    wrapper = _PreviewWrapper("taeh3.safetensors", "16", 512, 80, 1)
    result = wrapper(Executor(), "noise", callback=lambda *_: None)

    assert result == "next-wrapper"
    assert len(calls) == 1
    assert callable(calls[0][1]["callback"])


def test_preview_attach_reuses_one_wrapper_model(monkeypatch) -> None:
    class WrappersMP:
        OUTER_SAMPLE = "outer_sample"

    patcher_module = ModuleType("comfy.patcher_extension")
    patcher_module.WrappersMP = WrappersMP
    comfy_module = ModuleType("comfy")
    comfy_module.__path__ = []
    comfy_module.patcher_extension = patcher_module
    folder_module = ModuleType("folder_paths")
    folder_module.get_full_path = lambda category, name: f"/models/{category}/{name}"
    monkeypatch.setitem(sys.modules, "comfy", comfy_module)
    monkeypatch.setitem(sys.modules, "comfy.patcher_extension", patcher_module)
    monkeypatch.setitem(sys.modules, "folder_paths", folder_module)
    monkeypatch.setattr(preview_module, "_PREVIEW_MODEL_CACHE_KEY", None)
    monkeypatch.setattr(preview_module, "_PREVIEW_MODEL_CACHE_VALUE", None)

    clones = []

    class Clone:
        def __init__(self):
            self.wrappers = []

        def remove_wrappers_with_key(self, wrapper_type, key):
            self.wrappers = [item for item in self.wrappers if item[:2] != (wrapper_type, key)]

        def add_wrapper_with_key(self, wrapper_type, key, wrapper):
            self.wrappers.append((wrapper_type, key, wrapper))

    class Model:
        def clone(self):
            value = Clone()
            clones.append(value)
            return value

    model = Model()
    first = H3StudioTAEH3Preview.attach(model, True, "taeh3.safetensors", 512, 80, 1, "16")[0]
    second = H3StudioTAEH3Preview.attach(model, True, "taeh3.safetensors", 512, 80, 1, "16")[0]

    assert first is second
    assert len(clones) == 1
    assert len(first.wrappers) == 1
