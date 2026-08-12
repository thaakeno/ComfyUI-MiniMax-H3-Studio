from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from h3studio import runtime_handoff


class Patcher:
    def __init__(self, loaded=8 * 1024**3):
        self.loaded = loaded

    def loaded_size(self):
        return self.loaded


def _manager(monkeypatch, calls):
    comfy = ModuleType("comfy")
    comfy.__path__ = []
    manager = ModuleType("comfy.model_management")

    def unload_model_and_clones(patcher, unload_additional_models=True):
        calls.append((patcher, unload_additional_models))
        patcher.loaded = 0

    manager.unload_model_and_clones = unload_model_and_clones
    comfy.model_management = manager
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.model_management", manager)
    return manager


def test_release_uses_targeted_comfy_manager_api(monkeypatch) -> None:
    calls = []
    _manager(monkeypatch, calls)
    patcher = Patcher()

    result = runtime_handoff.release_stage_patcher(patcher, label="text_encoder")

    assert result.mode == "released"
    assert result.loaded_before == 8 * 1024**3
    assert result.loaded_after == 0
    assert calls == [(patcher, False)]


def test_release_can_be_disabled_for_ab(monkeypatch) -> None:
    calls = []
    _manager(monkeypatch, calls)
    monkeypatch.setenv("H3STUDIO_DISABLE_STAGE_HANDOFFS", "1")

    result = runtime_handoff.release_stage_patcher(Patcher(), label="vae")

    assert result.mode == "disabled-by-env"
    assert calls == []


def test_post_sampling_release_runs_even_when_sampling_raises(monkeypatch) -> None:
    calls = []
    _manager(monkeypatch, calls)
    patcher = Patcher()
    wrapper = runtime_handoff._ReleaseAfterSampling(patcher)

    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        wrapper(explode, None, None, None, None, None, None, False, 1, [])

    assert calls == [(patcher, False)]
    assert patcher.loaded == 0


def test_attach_sampling_release_is_idempotent(monkeypatch) -> None:
    patcher_extension = ModuleType("comfy.patcher_extension")
    patcher_extension.WrappersMP = SimpleNamespace(OUTER_SAMPLE="outer")
    comfy = ModuleType("comfy")
    comfy.__path__ = []
    comfy.patcher_extension = patcher_extension
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.patcher_extension", patcher_extension)
    calls = []

    class Model:
        def remove_wrappers_with_key(self, wrapper_type, key):
            calls.append(("remove", wrapper_type, key))

        def add_wrapper_with_key(self, wrapper_type, key, wrapper):
            calls.append(("add", wrapper_type, key, type(wrapper).__name__))

    model = Model()
    assert runtime_handoff.attach_sampling_stage_release(model) == "manager-targeted"
    assert calls[0] == ("remove", "outer", runtime_handoff.POST_SAMPLE_RELEASE_KEY)
    assert calls[1][:3] == ("add", "outer", runtime_handoff.POST_SAMPLE_RELEASE_KEY)


def test_handoff_module_never_uses_patcher_partial_unload() -> None:
    import inspect

    source = inspect.getsource(runtime_handoff)
    assert ".partially_unload(" not in source
