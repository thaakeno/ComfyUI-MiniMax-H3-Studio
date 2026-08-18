from __future__ import annotations

import pytest

from h3studio.acceleration import PDDBackendError, _restore_stacked_bypass_injections
from h3studio.lora_stack import (
    MAX_CUSTOM_LORAS,
    MAX_LORA_STRENGTH,
    MIN_LORA_STRENGTH,
    CustomLoraSpec,
    apply_custom_lora_stack,
    normalize_custom_loras,
    resolve_custom_lora,
)
from h3studio.state import StudioState


def test_normalize_custom_loras_is_bounded_ordered_and_clamped() -> None:
    source = [
        {"name": "styles/a.safetensors", "strength": 9.0},
        {"name": "styles/b.safetensors", "strength": -9.0},
        {"name": "disabled.safetensors", "strength": 1.0, "enabled": False},
        {"name": "zero.safetensors", "strength": 0.0},
        {"name": "c.safetensors", "strength": 0.55},
        {"name": "d.safetensors", "strength": 1.25},
        {"name": "e.safetensors", "strength": 1.0},
        {"name": "ignored_after_limit.safetensors", "strength": 1.0},
    ]

    specs = normalize_custom_loras(source)

    # The UI payload is capped before inactive rows are filtered, so hidden
    # rows cannot smuggle an unbounded stack into the runtime.
    assert len(source[:MAX_CUSTOM_LORAS]) == MAX_CUSTOM_LORAS
    assert MIN_LORA_STRENGTH == 0.0
    assert MAX_LORA_STRENGTH == 3.0
    assert [spec.name for spec in specs] == [
        "styles/a.safetensors",
        "c.safetensors",
        "d.safetensors",
    ]
    assert [spec.strength for spec in specs] == [3.0, 0.55, 1.25]


def test_normalize_custom_loras_accepts_windows_paths_and_defaults_strength() -> None:
    specs = normalize_custom_loras([{"name": r"people\hero.safetensors", "strength": "bad"}])
    assert specs == (CustomLoraSpec("people/hero.safetensors", 1.0, True),)


def test_custom_lora_stack_survives_studio_state_json_roundtrip() -> None:
    payload = {
        "ui": {
            "advanced_open": True,
            "custom_loras": [
                {"name": "styles/anime.safetensors", "strength": 0.7, "enabled": True},
                {"name": "characters/hero.safetensors", "strength": 1.15, "enabled": False},
            ],
        }
    }
    restored = StudioState.from_json(StudioState.from_dict(payload).to_json())

    assert restored.ui["advanced_open"] is True
    assert restored.ui["custom_loras"] == payload["ui"]["custom_loras"]


def test_resolve_custom_lora_prefers_exact_relative_path() -> None:
    choices = ["styles/foo.safetensors", "characters/foo.safetensors", "bar.safetensors"]
    assert resolve_custom_lora(choices, "styles/foo.safetensors") == "styles/foo.safetensors"
    assert resolve_custom_lora(choices, "bar.safetensors") == "bar.safetensors"


def test_resolve_custom_lora_allows_unique_basename_only() -> None:
    choices = ["styles/foo.safetensors", "bar.safetensors"]
    assert resolve_custom_lora(choices, "foo.safetensors") == "styles/foo.safetensors"


def test_resolve_custom_lora_rejects_ambiguous_or_missing_files() -> None:
    choices = ["styles/foo.safetensors", "characters/foo.safetensors"]
    with pytest.raises(PDDBackendError, match="ambiguous"):
        resolve_custom_lora(choices, "foo.safetensors")
    with pytest.raises(PDDBackendError, match="not available"):
        resolve_custom_lora(choices, "missing.safetensors")


def test_acceleration_lora_cannot_be_stacked_twice() -> None:
    specs = (CustomLoraSpec("nested/lightx.safetensors", 0.8),)
    with pytest.raises(PDDBackendError, match="Speed profile already applies"):
        apply_custom_lora_stack(
            object(),
            specs,
            reserved_artifacts=("lightx.safetensors",),
        )


def test_bypass_injections_are_composed_and_ejected_in_reverse_order() -> None:
    events: list[str] = []

    class FakeInjection:
        def __init__(self, name: str):
            self.name = name

        def inject(self, _patcher):
            events.append(f"inject:{self.name}")

        def eject(self, _patcher):
            events.append(f"eject:{self.name}")

    class FakePatcher:
        def __init__(self, current):
            self.injections = {"bypass_lora": list(current)}

        def get_injections(self, key):
            return self.injections.get(key)

        def set_injections(self, key, value):
            self.injections[key] = list(value)

    lightx = FakeInjection("lightx")
    style_a = FakeInjection("style-a")
    custom_new = FakeInjection("custom-new")
    patcher = FakePatcher([custom_new])

    count = _restore_stacked_bypass_injections(patcher, (lightx, style_a))

    assert count == 3
    assert len(patcher.injections["bypass_lora"]) == 1
    composite = patcher.injections["bypass_lora"][0]
    assert tuple(composite._h3studio_bypass_children) == (lightx, style_a, custom_new)

    composite.inject(patcher)
    composite.eject(patcher)
    assert events == [
        "inject:lightx",
        "inject:style-a",
        "inject:custom-new",
        "eject:custom-new",
        "eject:style-a",
        "eject:lightx",
    ]


def test_bypass_forward_stack_survives_repeated_generation_cycles() -> None:
    class FakeModule:
        pass

    module = FakeModule()

    def base_forward(value):
        return value

    module.forward = base_forward

    class ForwardWrapperInjection:
        def __init__(self):
            self.original_forward = None
            self.wrapper = None

        def inject(self, _patcher):
            if self.original_forward is not None:
                return
            self.original_forward = module.forward

            def wrapped(value):
                return self.original_forward(value) + 1

            self.wrapper = wrapped
            module.forward = wrapped

        def eject(self, _patcher):
            if self.original_forward is None:
                return
            module.forward = self.original_forward
            self.original_forward = None

    class FakePatcher:
        def __init__(self, current):
            self.injections = {"bypass_lora": list(current)}

        def get_injections(self, key):
            return self.injections.get(key)

        def set_injections(self, key, value):
            self.injections[key] = list(value)

    first = ForwardWrapperInjection()
    second = ForwardWrapperInjection()
    patcher = FakePatcher([second])
    assert _restore_stacked_bypass_injections(patcher, (first,)) == 2
    composite = patcher.injections["bypass_lora"][0]

    # This is the failure mode from the real traceback. With Comfy's normal
    # forward-order top-level ejection, the first wrapper is restored after its
    # owner has cleared original_forward; the next injection then captures its
    # own wrapper as original_forward and recurses forever. The composite must
    # survive many generation-style inject/eject cycles without leaving a hook.
    for _ in range(200):
        composite.inject(patcher)
        assert module.forward(7) == 9
        composite.eject(patcher)
        assert module.forward is base_forward
        assert module.forward(7) == 7
