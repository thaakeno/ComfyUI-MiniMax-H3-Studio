from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from h3studio.performance import ResidencyResult, force_full_residency, release_patcher, text_encoder_residency


class FakePatcher:
    load_device = SimpleNamespace(type="cpu")

    def model_size(self):
        return 12 * 1024**3

    def loaded_size(self):
        return 12 * 1024**3


def _install_fake_manager(monkeypatch, *, fail=False):
    comfy = ModuleType("comfy")
    manager = ModuleType("comfy.model_management")
    calls = []

    def load_models_gpu(models, **kwargs):
        calls.append(("load", tuple(models), dict(kwargs)))
        if fail:
            raise RuntimeError("synthetic full-load failure")

    def get_free_memory(_device):
        return 8 * 1024**3

    def soft_empty_cache():
        calls.append(("empty",))

    def unload_model_and_clones(patcher, **kwargs):
        calls.append(("unload", patcher, dict(kwargs)))
        return True

    manager.load_models_gpu = load_models_gpu
    manager.get_free_memory = get_free_memory
    manager.soft_empty_cache = soft_empty_cache
    manager.unload_model_and_clones = unload_model_and_clones
    manager.get_torch_device = lambda: FakePatcher.load_device
    manager.is_oom = lambda _exc: False
    comfy.model_management = manager
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.model_management", manager)
    return calls


def test_force_full_residency_uses_comfy_full_load(monkeypatch) -> None:
    calls = _install_fake_manager(monkeypatch)
    patcher = FakePatcher()

    result = force_full_residency(patcher, label="diffusion")

    assert result.mode == "full"
    assert result.model_bytes == 12 * 1024**3
    load = next(call for call in calls if call[0] == "load")
    assert load[1] == (patcher,)
    assert load[2]["force_full_load"] is True
    assert "diffusion_residency=full" in result.summary()


def test_full_residency_failure_is_nonfatal_dynamic_fallback(monkeypatch) -> None:
    _install_fake_manager(monkeypatch, fail=True)
    result = force_full_residency(FakePatcher(), label="text_encoder")
    assert result.mode == "dynamic-fallback"
    assert "fallback=RuntimeError" in result.summary()


def test_targeted_release_does_not_globally_unload_models(monkeypatch) -> None:
    calls = _install_fake_manager(monkeypatch)
    patcher = FakePatcher()
    result = ResidencyResult("vae", "full")

    elapsed = release_patcher(patcher, result)

    assert elapsed >= 0
    unload = next(call for call in calls if call[0] == "unload")
    assert unload[1] is patcher
    assert unload[2] == {"unload_additional_models": False}
    assert any(call[0] == "empty" for call in calls)


def test_text_encoder_full_load_happens_only_at_native_clip_boundary(monkeypatch) -> None:
    calls = _install_fake_manager(monkeypatch)
    patcher = FakePatcher()
    original_calls = []

    class CondStage:
        @staticmethod
        def memory_estimation_function(tokens, device=None):
            assert tokens == {"tokens": 1}
            assert device is patcher.load_device
            return 321

    class Clip:
        def __init__(self):
            self.patcher = patcher
            self.cond_stage_model = CondStage()

        def load_model(self, tokens=None):
            original_calls.append(tokens)
            return self.patcher

    clip = Clip()
    with text_encoder_residency(clip) as result:
        assert not [call for call in calls if call[0] == "load"]
        returned = clip.load_model({"tokens": 1})
        assert returned is patcher

    loads = [call for call in calls if call[0] == "load"]
    assert len(loads) == 1
    assert loads[0][1] == (patcher,)
    assert loads[0][2] == {"memory_required": 321, "force_full_load": True}
    assert original_calls == []
    assert result.mode == "native-full"
    assert any(call[0] == "unload" for call in calls)
