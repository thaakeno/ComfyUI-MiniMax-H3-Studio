from __future__ import annotations

from dataclasses import replace

import pytest

from h3studio.errors import MissingReferenceError
from h3studio.references import (
    ReferenceImage,
    compile_mentions,
    infer_role,
    infer_roles_from_prompt,
    iter_mentions,
    mention_ordinals,
    normalize_references,
    rewrite_mentions,
    validate_mentions,
)


def reference(ordinal: int, **kwargs) -> ReferenceImage:
    return ReferenceImage(
        id=kwargs.pop("id", f"ref_{ordinal}"),
        filename=kwargs.pop("filename", f"image_{ordinal}.png"),
        ordinal=ordinal,
        **kwargs,
    )


def test_iter_mentions_accepts_spacing_and_case() -> None:
    mentions = list(iter_mentions("Use @Image1, @image 2 and @IMAGE   9."))
    assert [item.ordinal for item in mentions] == [1, 2, 9]
    assert mentions[0].source == "@Image1"


def test_mentions_do_not_match_email_or_double_at() -> None:
    assert mention_ordinals("mail me@Image 1 or type @@Image 2") == []


def test_mention_ordinals_are_unique_in_first_seen_order() -> None:
    assert mention_ordinals("@Image 3 @Image 1 @Image 3 @Image 2") == [3, 1, 2]
    assert mention_ordinals("@Image 3 @Image 1 @Image 3", unique=False) == [3, 1, 3]


def test_compile_mentions_uses_native_picture_tags() -> None:
    refs = (reference(1), reference(2))
    assert compile_mentions("Style @Image 1; identity @Image2.", refs) == "Style <Picture 1>; identity <Picture 2>."


def test_compile_mentions_can_emit_subject_tags() -> None:
    assert compile_mentions("Keep @Image 1", (reference(1),), tag="subject") == "Keep <Subject 1>"


def test_compile_mentions_rejects_disconnected_reference() -> None:
    with pytest.raises(MissingReferenceError, match="not connected"):
        compile_mentions("Use @Image 2", (reference(1),))


def test_disabled_reference_is_treated_as_missing() -> None:
    with pytest.raises(MissingReferenceError):
        compile_mentions("Use @Image 1", (reference(1, enabled=False),))


def test_rewrite_mentions_after_reorder() -> None:
    prompt = "Use @Image 1 for style and @Image2 for identity."
    assert rewrite_mentions(prompt, {1: 2, 2: 1}) == "Use @Image 2 for style and @Image 1 for identity."


def test_normalize_references_renumbers_and_limits() -> None:
    refs = [ReferenceImage(f"ref_{index}", f"image_{index}.png", index + 4) for index in range(1, 12)]
    normalized = normalize_references(refs)
    assert len(normalized) == 9
    assert [item.ordinal for item in normalized] == list(range(1, 10))


def test_duplicate_reference_ids_are_repaired_non_strict() -> None:
    normalized = normalize_references((reference(1, id="same"), reference(2, id="same")))
    assert normalized[0].id == "same"
    assert normalized[1].id != "same"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("keep the same face and jaw", "face"),
        ("copy the dramatic poster composition", "composition"),
        ("transfer the cel-shaded anime linework style", "style"),
        ("preserve the jacket and wardrobe", "outfit"),
        ("match the title typography", "typography"),
    ],
)
def test_role_inference(text: str, expected: str) -> None:
    assert infer_role(text) == expected


def test_role_inference_respects_explicit_role() -> None:
    refs = (reference(1, role="identity"),)
    inferred = infer_roles_from_prompt("Use @Image 1 for style", refs)
    assert inferred[0].role == "identity"


def test_prompt_repairs_auto_role_after_visual_analysis() -> None:
    refs = (
        replace(reference(1), role="reference", role_auto=True, retention_auto=True, tags=("visually_analyzed",)),
        replace(reference(2), role="reference", role_auto=True, retention_auto=True, tags=("visually_analyzed",)),
    )
    inferred = infer_roles_from_prompt(
        "Show the man from @Image1 holding the fluffy thing from @Image2 in both hands",
        refs,
    )
    assert inferred[0].role == "character"
    assert inferred[1].role == "object"


def test_role_inference_uses_nearby_mention_language() -> None:
    refs = (reference(1), reference(2))
    inferred = infer_roles_from_prompt(
        "Use @Image 1 for the character identity. Apply the poster layout and typography from @Image 2.", refs
    )
    assert inferred[0].role in {"identity", "character"}
    assert inferred[1].role in {"layout", "typography", "composition"}


def test_validate_mentions_returns_actionable_diagnostic() -> None:
    diagnostics = validate_mentions("Use @Image 4", (reference(1),))
    assert diagnostics.has_errors
    assert diagnostics.items[0].code == "missing_reference"
    assert diagnostics.items[0].field == "prompt"
