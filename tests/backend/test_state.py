from __future__ import annotations

import json

import pytest

from h3studio.constants import MAX_MEGAPIXELS, STATE_SCHEMA_VERSION
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


def test_reference_content_identity_and_thumbnail_round_trip() -> None:
    reference = ReferenceImage(
        "ref",
        "portrait.png",
        1,
        width=1080,
        height=1920,
        fingerprint="pixels-abc",
        thumbnail="/view?filename=portrait.png",
        tags=("visually_analyzed", "role_origin:vision"),
    )
    restored = StudioState.from_json(StudioState(references=(reference,)).to_json()).references[0]

    assert restored.width == 1080
    assert restored.height == 1920
    assert restored.fingerprint == "pixels-abc"
    assert restored.thumbnail == "/view?filename=portrait.png"
    assert restored.tags == ("visually_analyzed", "role_origin:vision")


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
    assert migrated["schema_version"] == STATE_SCHEMA_VERSION
    assert migrated["generation"]["seed"] == 9
    assert migrated["generation"]["cap_native_resolution"] is False
    assert migrated["prompt_options"]["enhance_mode"] == "off"


def test_generation_options_clamp_values() -> None:
    options = GenerationOptions.from_dict({"seed": -4, "megapixels": 999, "custom_width": 1})
    assert options.seed == 0
    assert options.megapixels == MAX_MEGAPIXELS
    assert options.custom_width == 32


def test_seed_lock_round_trips_and_schema9_defaults_unlocked() -> None:
    locked = GenerationOptions.from_dict({"seed": 987, "seed_locked": True})
    assert GenerationOptions.from_dict(locked.as_dict()).seed_locked is True
    migrated = StudioState.from_dict({"schema_version": 9, "generation": {"seed": 42}})
    assert migrated.generation.seed == 42
    assert migrated.generation.seed_locked is False


def test_schema8_native_cap_migrates_to_direct_two_megapixel_canvas() -> None:
    state = StudioState.from_dict({
        "schema_version": 8,
        "generation": {"aspect_ratio": "1:1", "megapixels": 2.0, "cap_native_resolution": True},
    })
    assert state.generation.cap_native_resolution is False
    assert (state.generation.resolution().width, state.generation.resolution().height) == (1408, 1408)


def test_prompt_options_clamp_and_validate() -> None:
    options = PromptOptions.from_dict(
        {"adherence": 8, "detail_level": "unknown", "analyzer_max_tokens": 4, "analyzer_resolution": 9999}
    )
    assert options.adherence == 1.0
    assert options.detail_level == "detailed"
    assert options.analyzer_max_tokens == 128
    assert options.analyzer_resolution == 1024
    assert PromptOptions.from_dict({"analyzer_resolution": 0}).analyzer_resolution == 0


def test_legacy_vlm_migrates_to_analysis_toggle_and_structured_format() -> None:
    options = PromptOptions.from_dict({"enhance_mode": "vlm"})
    assert options.enhance_mode == "compile_only"
    assert options.analyze_images is True


def test_json_payload_is_compact_by_default() -> None:
    payload = StudioState(prompt="x").to_json()
    assert "\n" not in payload
    assert json.loads(payload)["prompt"] == "x"
