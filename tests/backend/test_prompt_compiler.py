from __future__ import annotations

import pytest

from h3studio.constants import ENHANCE_OFF, ENHANCE_SINGLE, MODE_TEXT_TO_IMAGE
from h3studio.errors import PromptFormatError
from h3studio.prompting.compiler import PromptCompiler, normalize_user_prompt, resolve_mode
from h3studio.prompting.sections import ImagePromptSections
from h3studio.prompting.vlm import compile_with_optional_vlm
from h3studio.references import ReferenceImage
from h3studio.state import GenerationOptions, PromptOptions, StudioState


def ref(ordinal: int, role: str = "auto", retention: str = "attribute_transfer") -> ReferenceImage:
    return ReferenceImage(f"r{ordinal}", f"ref{ordinal}.png", ordinal, role=role, retention=retention)


def test_normalize_user_prompt() -> None:
    assert normalize_user_prompt("  hello   world\r\n\r\n\r\nnext  ") == "hello world\n\nnext"


@pytest.mark.parametrize(
    "token",
    ["@image_1", "H3STUDIO_REF_1", "__H3STUDIO_REF_1__", "**H3STUDIO\\_REF\\_1**"],
)
def test_normalize_all_editor_reference_tokens(token: str) -> None:
    assert normalize_user_prompt(f"change his hair to green {token}") == "change his hair to green @Image1"


@pytest.mark.parametrize(
    ("references", "expected"),
    [(0, "text_to_image"), (1, "image_to_image"), (2, "reference_edit")],
)
def test_auto_mode_resolution(references: int, expected: str) -> None:
    assert resolve_mode("auto", references) == expected


def test_explicit_mode_wins() -> None:
    assert resolve_mode(MODE_TEXT_TO_IMAGE, 4) == MODE_TEXT_TO_IMAGE


def test_compile_t2i_has_exactly_four_sections() -> None:
    result = PromptCompiler().compile(StudioState(prompt="A cheerful cartoon sponge builds a giant burger."))
    assert result.resolved_mode == "text_to_image"
    assert list(result.sections.as_dict()) == [
        "subject_definitions",
        "summary",
        "retention_analysis",
        "detailed_description",
    ]
    assert "overall_soundscape" not in result.rendered
    assert "non_diegetic_music" not in result.rendered


def test_missing_optional_vlm_falls_back_to_compiler() -> None:
    state = StudioState(
        prompt="A clean studio portrait.",
        prompt_options=PromptOptions(enhance_mode="vlm", analyzer_model=""),
    )
    result, note = compile_with_optional_vlm(state, [], compiler=PromptCompiler())
    assert result.native_prompt
    assert "production-brief compiler" in note


def test_compile_reference_prompt_uses_native_tags() -> None:
    state = StudioState(
        prompt="Use @Image 1 for style and preserve @Image 2 as the character.",
        references=(ref(1, "style"), ref(2, "identity", "fully_preserved")),
    )
    result = PromptCompiler().compile(state)
    assert result.resolved_mode == "reference_edit"
    assert "<Subject 1> is rendering language" in result.native_prompt
    assert "sourced from <Picture 1>" in result.native_prompt
    assert "<Subject 2>" in result.native_prompt
    assert "sourced from <Picture 2>" in result.native_prompt
    assert "@Image" not in result.native_prompt
    assert "fully_preserved" in result.native_prompt


def test_easy_runtime_tokens_and_zero_width_chip_spacing_compile_to_native_ids() -> None:
    state = StudioState(
        prompt=(
            "Show the person from\u200b \u200b__H3STUDIO_REF_2__\u200b with the clothes in "
            "\u200b__H3STUDIO_REF_1__\u200b somewhere outside"
        ),
        references=(ref(1), ref(2)),
    )
    result = PromptCompiler().compile(state)
    assert "__H3STUDIO" not in result.native_prompt
    assert "<Subject 1>" in result.native_prompt
    assert "<Picture 1>" in result.native_prompt
    assert "<Subject 2>" in result.native_prompt
    assert "<Picture 2>" in result.native_prompt
    assert result.references[0].role == "outfit"
    assert result.references[1].role in {"character", "identity"}
    assert "not a reference sheet or collage" in result.native_prompt
    assert "extra people" in result.native_prompt


def test_single_reference_edit_is_a_locked_fl2va_source() -> None:
    state = StudioState(prompt="change his hair to green @image_1", references=(ref(1),))
    result = PromptCompiler().compile(state)
    assert result.resolved_mode == "image_to_image"
    assert "<Picture 1> is the single source image and locked canvas" in result.native_prompt
    assert "preserve every unmentioned" in result.native_prompt.lower()
    assert "fully_preserved" in result.native_prompt
    assert "attribute_transfer" not in result.native_prompt
    assert "H3STUDIO" not in result.native_prompt
    assert result.references[0].role == "face"
    assert result.references[0].role_auto is True
    assert result.references[0].retention == "fully_preserved"
    assert result.references[0].retention_auto is True


def test_keep_prompt_does_not_add_structure() -> None:
    state = StudioState(
        prompt="change his hair to green @image_1",
        references=(ref(1),),
        prompt_options=PromptOptions(enhance_mode=ENHANCE_OFF),
    )
    result = PromptCompiler().compile(state)
    assert result.native_prompt == "change his hair to green <Picture 1>"
    assert "subject_definitions" not in result.native_prompt


def test_single_prompt_is_one_line_and_explicit_for_source_edit() -> None:
    state = StudioState(
        prompt="change his hair to green @image_1",
        references=(ref(1),),
        prompt_options=PromptOptions(enhance_mode=ENHANCE_SINGLE),
    )
    result = PromptCompiler().compile(state)
    assert "\n" not in result.native_prompt
    assert result.native_prompt.startswith(
        "Edit <Picture 1>, the single locked source image: change his hair to green."
    )
    assert "Preserve the same identity" in result.native_prompt
    assert "reference sheet" in result.native_prompt


def test_single_prompt_assigns_multi_reference_roles_to_stable_subjects() -> None:
    state = StudioState(
        prompt="Show the person from @Image2 with the clothes in @Image1 somewhere outside",
        references=(ref(1), ref(2)),
        prompt_options=PromptOptions(enhance_mode=ENHANCE_SINGLE),
    )
    result = PromptCompiler().compile(state)
    assert "\n" not in result.native_prompt
    assert "<Subject 1>, sourced from <Picture 1>, supplies wardrobe" in result.native_prompt
    assert "<Subject 2>, sourced from <Picture 2>, supplies character identity" in result.native_prompt
    assert "floating garments" in result.native_prompt
    assert "<Subject 1>" in result.native_prompt


def test_reference_only_state_uses_official_weak_reference_marker_in_native_prompt() -> None:
    manual = ReferenceImage(
        "manual",
        "manual.png",
        1,
        role="style",
        retention="reference_only",
        role_auto=False,
        retention_auto=False,
    )
    result = PromptCompiler().compile(
        StudioState(
            prompt="Use @Image1 as broad visual inspiration alongside @Image2",
            references=(manual, ref(2, "identity", "fully_preserved")),
        )
    )
    assert "<Subject 1>: weak_reference" in result.native_prompt
    assert result.references[0].retention == "reference_only"


def test_single_prompt_includes_visual_analyzer_descriptions() -> None:
    references = (
        ReferenceImage("person", "person.png", 1, role="character", description="a pale clown with red hair"),
        ReferenceImage("glasses", "glasses.png", 2, role="object", description="black rectangular glasses"),
    )
    state = StudioState(
        prompt="Show @Image1 wearing @Image2",
        references=references,
        prompt_options=PromptOptions(enhance_mode=ENHANCE_SINGLE, analyze_images=True),
    )
    result = PromptCompiler().compile(state)
    assert "a pale clown with red hair" in result.native_prompt
    assert "black rectangular glasses" in result.native_prompt
    assert "\n" not in result.native_prompt


def test_compile_warns_when_connected_references_are_not_mentioned() -> None:
    result = PromptCompiler().compile(StudioState(prompt="Make a portrait", references=(ref(1, "identity"),)))
    assert any(item.code == "references_not_mentioned" for item in result.diagnostics)


def test_unmentioned_auto_reference_is_not_promoted_to_identity_retention() -> None:
    analyzed = ReferenceImage(
        "person",
        "person.png",
        1,
        role="identity",
        retention="fully_preserved",
        role_auto=True,
        retention_auto=True,
        tags=("visually_analyzed",),
    )
    result = PromptCompiler().compile(
        StudioState(
            prompt="Make an unrelated landscape",
            references=(analyzed,),
            generation=GenerationOptions(mode="reference_edit"),
        )
    )

    assert result.references[0].role == "reference"
    assert result.references[0].retention == "reference_only"


def test_manual_role_and_retention_remain_authoritative() -> None:
    manual = ReferenceImage(
        "manual",
        "manual.png",
        1,
        role="style",
        retention="reference_only",
        role_auto=False,
        retention_auto=False,
    )
    result = PromptCompiler().compile(
        StudioState(prompt="Preserve the person identity from @Image1", references=(manual,))
    )

    assert result.references[0].role == "style"
    assert result.references[0].retention == "reference_only"
    assert "role_origin:manual" in result.references[0].tags
    assert "retention_origin:manual" in result.references[0].tags


def test_multiple_explicit_identity_sources_can_be_fully_preserved() -> None:
    state = StudioState(
        prompt="Show the same person from @Image1 beside the same character from @Image2.",
        references=(ref(1), ref(2)),
    )
    result = PromptCompiler().compile(state)

    assert all(item.role in {"identity", "character"} for item in result.references)
    assert all(item.retention == "fully_preserved" for item in result.references)


def test_compile_rejects_empty_prompt() -> None:
    with pytest.raises(PromptFormatError, match="empty"):
        PromptCompiler().compile(StudioState())


def test_compile_rejects_missing_mentioned_reference() -> None:
    with pytest.raises(PromptFormatError, match="missing_reference"):
        PromptCompiler().compile(StudioState(prompt="Use @Image 2", references=(ref(1),)))


def test_explicit_t2i_ignores_references_with_warning() -> None:
    state = StudioState(
        prompt="Create something new",
        references=(ref(1),),
        generation=GenerationOptions(mode="text_to_image"),
    )
    result = PromptCompiler().compile(state)
    assert result.resolved_mode == "text_to_image"
    assert any(item.code == "references_ignored_in_t2i" for item in result.diagnostics)


def test_adherence_changes_discipline_text() -> None:
    strict_state = StudioState(prompt="A portrait", prompt_options=PromptOptions(adherence=0.95))
    loose_state = StudioState(prompt="A portrait", prompt_options=PromptOptions(adherence=0.2))
    assert "strict constraints" in PromptCompiler().compile(strict_state).rendered
    assert "substantial visual interpretation" in PromptCompiler().compile(loose_state).rendered


def test_directional_gaze_becomes_a_hard_frame_constraint() -> None:
    state = StudioState(
        prompt="Show the person in @Image1 with the glasses from @Image2 and make him look to the right",
        references=(ref(1), ref(2)),
    )
    result = PromptCompiler().compile(state)
    assert "turn the head and direct the eyes toward frame-right" in result.native_prompt
    assert "do not preserve a frontal head direction or frontal gaze" in result.native_prompt


def test_accept_enhanced_normalizes_sections() -> None:
    base = PromptCompiler().compile(StudioState(prompt="A poster"))
    enhanced = """subject_definitions:
N/A - no references.

summary:
[image generation] A dramatic poster.

retention_analysis:
N/A - no references.

detailed_description:
A centered dramatic poster with controlled typography.
"""
    result = PromptCompiler().accept_enhanced(enhanced, base)
    assert result.rendered.startswith("subject_definitions:")
    assert result.sections.summary.startswith("[image generation]")


def test_sections_reject_audio_fields_when_strict() -> None:
    value = """subject_definitions:
none
summary:
image
retention_analysis:
none
detailed_description:
still
overall_soundscape:
N/A
"""
    with pytest.raises(PromptFormatError, match="audio sections"):
        ImagePromptSections.parse(value, strict=True)
