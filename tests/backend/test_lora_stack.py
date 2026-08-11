from __future__ import annotations

import pytest

from h3studio.acceleration import PDDBackendError, _restore_stacked_bypass_injections
from h3studio.lora_stack import (
    MAX_CUSTOM_LORAS,
    CustomLoraSpec,
    apply_custom_lora_stack,
    normalize_custom_loras,
    resolve_custom_lora,
)


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
    assert [spec.name for spec in specs] == [
        "styles/a.safetensors",
        "styles/b.safetensors",
        "c.safetensors",
        "d.safetensors",
    ]
    assert [spec.strength for spec in specs] == [4.0, -4.0, 0.55, 1.25]


def test_normalize_custom_loras_accepts_windows_paths_and_defaults_strength() -> None:
    specs = normalize_custom_loras([{"name": r"people\hero.safetensors", "strength": "bad"}])
    assert specs == (CustomLoraSpec("people/hero.safetensors", 1.0, True),)


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


def test_bypass_injections_are_additive_instead_of_last_lora_wins() -> None:
    class FakePatcher:
        def __init__(self):
            self.injections = {"bypass_lora": ["custom-new"]}

        def get_injections(self, key):
            return self.injections.get(key)

        def set_injections(self, key, value):
            self.injections[key] = list(value)

    patcher = FakePatcher()
    count = _restore_stacked_bypass_injections(patcher, ("lightx", "style-a"))

    assert count == 3
    assert patcher.injections["bypass_lora"] == ["lightx", "style-a", "custom-new"]
