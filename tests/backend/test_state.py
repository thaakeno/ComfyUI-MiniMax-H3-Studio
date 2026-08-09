from __future__ import annotations

import json

import pytest

from h3studio.constants import STATE_SCHEMA_VERSION
from h3studio.errors import StateDecodeError, StateVersionError
from h3studio.references import ReferenceImage
from h3studio.state import GenerationOptions, PromptOptions, StudioState, migrate_state_dict


def test_empty_state_round_trip() -> None:
    state = StudioState()
    assert StudioState.from_json(state.to_json()) == state


def test_unicode_prompt_round_trip() -> None:
    state = StudioState(prompt="雨の東京 — cinematic café")
    restored = StudioState.from_json(state.to_json())
    assert restored.prompt == state.prompt


def test_reference_round_trip() -> None:
    state = StudioState(
        prompt="Use @Image 1",
        references=(ReferenceImage("ref", "portrait.png", 1, role="identity", description="a woman"),),
    )
    restored = StudioState.from_json(state.to_json(pretty=True))
    assert restored.references[0].role == "identity"
    assert restored.references[0].description == "a woman"


def test_uploaded_reference_storage_round_trip() -> None:
    state = StudioState(
        references=(ReferenceImage("ref", "portrait.png", 1, storage_name="h3studio/portrait.png"),),
    )
    restored = StudioState.from_json(state.to_json())
    assert restored.references[0].filename == "portrait.png"
    assert restored.references[0].storage_name == "h3studio/portrait.png"


def test_invalid_json_raises_domain_error() -> None:
    with pytest.raises(StateDecodeError):
        StudioState.from_json("not json")


def test_non_object_json_raises() -> None:
    with pytest.raises(StateDecodeError):
        StudioState.from_json("[]")


def test_future_schema_is_rejected() -> None:
    with pytest.raises(StateVersionError, match="Update"):
        StudioState.from_dict({"schema_version": STATE_SCHEMA_VERSION + 1})


def test_v1_settings_are_migrated() -> None:
    old = {
        "schema_version": 1,
        "prompt": "hello",
        "settings": {"mode": "text_to_image", "seed": 9, "enhance_mode": "off", "adherence": 0.4},
    }
    migrated = migrate_state_dict(old)
    assert migrated["schema_version"] == 5
    assert migrated["generation"]["seed"] == 9
    assert migrated["prompt_options"]["enhance_mode"] == "off"


def test_generation_options_clamp_values() -> None:
    options = GenerationOptions.from_dict({"seed": -4, "megapixels": 999, "custom_width": 1})
    assert options.seed == 0
    assert options.megapixels == 2.0
    assert options.custom_width == 32


def test_prompt_options_clamp_and_validate() -> None:
    options = PromptOptions.from_dict({"adherence": 8, "detail_level": "unknown", "analyzer_max_tokens": 4})
    assert options.adherence == 1.0
    assert options.detail_level == "detailed"
    assert options.analyzer_max_tokens == 128


def test_json_payload_is_compact_by_default() -> None:
    payload = StudioState(prompt="x").to_json()
    assert "\n" not in payload
    assert json.loads(payload)["prompt"] == "x"
