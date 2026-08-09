from __future__ import annotations

import pytest

from h3studio.constants import MODE_TEXT_TO_IMAGE
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
    assert "<Picture 1>" in result.native_prompt
    assert "<Subject 2>" in result.native_prompt
    assert "@Image" not in result.native_prompt
    assert "fully_preserved" in result.native_prompt


def test_compile_warns_when_connected_references_are_not_mentioned() -> None:
    result = PromptCompiler().compile(StudioState(prompt="Make a portrait", references=(ref(1, "identity"),)))
    assert any(item.code == "references_not_mentioned" for item in result.diagnostics)


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
