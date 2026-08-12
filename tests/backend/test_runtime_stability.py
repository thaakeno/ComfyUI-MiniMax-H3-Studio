from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

# The runtime class intentionally subclasses Comfy-facing nodes. CI unit tests do
# not install ComfyUI itself, so provide the import-only module those nodes expect.
sys.modules.setdefault("folder_paths", ModuleType("folder_paths"))

from h3studio import runtime_stability


def test_accelerated_preview_is_intentionally_sparse() -> None:
    assert runtime_stability.accelerated_preview_steps(4) == frozenset({0})
    assert runtime_stability.accelerated_preview_steps(8) == frozenset({0})
    assert runtime_stability.accelerated_preview_steps(20) == frozenset(range(20))


def test_low_ram_enables_comfy_fast_disk(monkeypatch) -> None:
    comfy = ModuleType("comfy")
    manager = ModuleType("comfy.model_management")
    manager.args = SimpleNamespace(fast_disk=False, high_ram=False)
    comfy.model_management = manager
    psutil = ModuleType("psutil")
    psutil.virtual_memory = lambda: SimpleNamespace(total=32 * 1024**3)

    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.model_management", manager)
    monkeypatch.setitem(sys.modules, "psutil", psutil)
    monkeypatch.delenv("H3STUDIO_DISABLE_AUTO_FAST_DISK", raising=False)

    assert runtime_stability.configure_low_ram_fast_disk() == "enabled"
    assert manager.args.fast_disk is True


def test_high_ram_leaves_fast_disk_unchanged(monkeypatch) -> None:
    comfy = ModuleType("comfy")
    manager = ModuleType("comfy.model_management")
    manager.args = SimpleNamespace(fast_disk=False, high_ram=False)
    comfy.model_management = manager
    psutil = ModuleType("psutil")
    psutil.virtual_memory = lambda: SimpleNamespace(total=96 * 1024**3)

    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.model_management", manager)
    monkeypatch.setitem(sys.modules, "psutil", psutil)

    assert runtime_stability.configure_low_ram_fast_disk() == "not-needed"
    assert manager.args.fast_disk is False


def test_stable_sampling_removes_experimental_prepare_wrapper(monkeypatch) -> None:
    calls = []

    class Model:
        def remove_wrappers_with_key(self, wrapper, key):
            calls.append((wrapper, key))

    fake_model = Model()

    def parent_build(self, model, studio_context):
        return fake_model, "sampler", "sigmas", "base-info"

    monkeypatch.setattr(
        runtime_stability.H3StudioOptimizedContextSamplingPreset,
        "build",
        parent_build,
    )
    patcher_extension = ModuleType("comfy.patcher_extension")
    patcher_extension.WrappersMP = SimpleNamespace(PREPARE_SAMPLING="prepare-sampling")
    comfy = ModuleType("comfy")
    comfy.patcher_extension = patcher_extension
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.patcher_extension", patcher_extension)
    monkeypatch.delenv("H3STUDIO_EXPERIMENTAL_FULL_DIFFUSION", raising=False)

    model, sampler, sigmas, info = runtime_stability.H3StudioStableContextSamplingPreset().build(
        object(), object()
    )

    assert model is fake_model
    assert sampler == "sampler"
    assert sigmas == "sigmas"
    assert calls == [("prepare-sampling", runtime_stability.SAMPLING_RESIDENCY_WRAPPER_KEY)]
    assert "sampling_residency=native-comfy-manager" in info
