from __future__ import annotations

import sys
from types import ModuleType

import h3studio.nodes.preview as preview_module
from h3studio.nodes.preview import H3StudioTAEH3Preview, _limit_latent, _PreviewWrapper


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
    sigmas = [1.0, 0.5, 0.0]
    result = wrapper(Executor(), "noise", "latent", "sampler", sigmas, None, lambda *_: None, False, 42, [])

    assert result == "next-wrapper"
    assert len(calls) == 1
    assert callable(calls[0][0][5])
    assert calls[0][1] == {"latent_shapes": []}


def test_preview_callback_decodes_before_native_progress_can_reuse_x0(monkeypatch) -> None:
    torch_module = ModuleType("torch")
    monkeypatch.setitem(sys.modules, "torch", torch_module)
    order = []
    captured = {}

    class Executor:
        def __call__(self, *args, **kwargs):
            captured["callback"] = args[5]
            return "sampled"

    wrapper = _PreviewWrapper("taeh3.safetensors", "16", 768, 90, 1)
    monkeypatch.setattr(wrapper, "_enqueue", lambda *_args: order.append("preview-enqueued"))
    wrapper(
        Executor(), "noise", "latent", "sampler", [1.0, 0.5, 0.0], None,
        lambda *_args: order.append("native-progress"), False, 42, [],
    )
    captured["callback"](0, "x0", "x", 4)

    assert order == ["preview-enqueued", "native-progress"]


def test_packed_preview_slices_each_channel_before_reshape() -> None:
    from h3studio.nodes.preview import _resolve_packed_latent

    class Value:
        ndim = 3
        shape = (1, 2, 6)

        def __getitem__(self, key):
            assert key == (slice(None), slice(None), slice(None, 4))
            return self

        def reshape(self, shape):
            assert shape == (1, 2, 1, 2, 2)
            return "restored"

    assert _resolve_packed_latent(None, Value(), [(1, 2, 1, 2, 2)]) == "restored"


def test_preview_callback_reports_sampler_elapsed_and_average_step_time(monkeypatch) -> None:
    torch_module = ModuleType("torch")
    monkeypatch.setitem(sys.modules, "torch", torch_module)
    monkeypatch.setattr(preview_module.time, "perf_counter", iter((10.0, 14.0)).__next__)
    captured = {}

    class Executor:
        def __call__(self, *args, **kwargs):
            captured["callback"] = args[5]
            return "sampled"

    wrapper = _PreviewWrapper("taeh3.safetensors", "16", 768, 90, 1)
    monkeypatch.setattr(wrapper, "_enqueue", lambda *args: captured.update(enqueue=args))
    wrapper(Executor(), "noise", "latent", "sampler", [1.0, 0.5, 0.0], None, None, False, 42, [])
    captured["callback"](1, "x0", "x", 4)

    assert captured["enqueue"][-2:] == (4.0, 2.0)


def test_preview_downscale_preserves_latent_aspect_ratio() -> None:
    captured = {}

    class Functional:
        @staticmethod
        def interpolate(value, *, size, mode, align_corners):
            captured.update(size=size, mode=mode, align_corners=align_corners)
            return "resized"

    class NN:
        functional = Functional()

    class Torch:
        nn = NN()

    class Latent:
        shape = (1, 24, 20, 10)

    assert _limit_latent(Torch(), Latent(), 160) == "resized"
    assert captured["size"] == (10, 5)


def test_preview_attach_refreshes_wrapper_for_each_execution(monkeypatch) -> None:
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

    assert first is not second
    assert len(clones) == 2
    assert len(first.wrappers) == 1
    assert len(second.wrappers) == 1
