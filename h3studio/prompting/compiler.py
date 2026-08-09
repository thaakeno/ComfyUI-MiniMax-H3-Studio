"""Deterministic four-section compiler used with or without a VLM."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from ..constants import (
    ENHANCE_OFF,
    ENHANCE_SINGLE,
    MODE_AUTO,
    MODE_IMAGE_TO_IMAGE,
    MODE_REFERENCE_EDIT,
    MODE_TEXT_TO_IMAGE,
)
from ..errors import Diagnostic, DiagnosticBag, PromptFormatError
from ..references import (
    ReferenceImage,
    compile_mentions,
    infer_roles_from_prompt,
    mention_ordinals,
    validate_mentions,
)
from ..state import StudioState
from .sections import ImagePromptSections
from .templates import ROLE_PHRASES

_SPACE_RE = re.compile(r"[ \t]+")
_BLANK_RE = re.compile(r"\n{3,}")
_INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_LEGACY_RUNTIME_REF_RE = re.compile(
    r"(?:\*\*|__)?H3STUDIO_REF_([1-9]\d*)(?:\*\*|__)?",
    re.IGNORECASE,
)


def _hard_constraints(prompt: str) -> tuple[str, ...]:
    """Translate easy-to-miss pose/gaze language into visible frame constraints."""

    lowered = str(prompt or "").lower()
    constraints: list[str] = []
    if re.search(r"\b(?:look|looking|gaze|face|turn(?:ed)?(?: his| her| their)? head)\b[^.!?]{0,35}\bto (?:the )?right\b", lowered):
        constraints.append(
            "The requested person must visibly turn the head and direct the eyes toward frame-right; "
            "do not preserve a frontal head direction or frontal gaze from any reference."
        )
    if re.search(r"\b(?:look|looking|gaze|face|turn(?:ed)?(?: his| her| their)? head)\b[^.!?]{0,35}\bto (?:the )?left\b", lowered):
        constraints.append(
            "The requested person must visibly turn the head and direct the eyes toward frame-left; "
            "do not preserve a frontal head direction or frontal gaze from any reference."
        )
    return tuple(constraints)


def normalize_user_prompt(value: str) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _INVISIBLE_RE.sub("", text)
    # Rich-text serializers may Markdown-escape underscores before sending a
    # mention chip back to Python (for example **H3STUDIO\_REF\_1**).
    text = text.replace("\\_", "_")
    text = _LEGACY_RUNTIME_REF_RE.sub(lambda match: f"@Image {match.group(1)}", text)
    text = re.sub(r"(?<![\w@])@image[_\s]*([1-9]\d*)\b", r"@Image \1", text, flags=re.IGNORECASE)
    text = "\n".join(_SPACE_RE.sub(" ", line).rstrip() for line in text.splitlines())
    return _BLANK_RE.sub("\n\n", text).strip()


def resolve_mode(requested: str, reference_count: int) -> str:
    if requested != MODE_AUTO:
        return requested
    if reference_count == 0:
        return MODE_TEXT_TO_IMAGE
    if reference_count == 1:
        return MODE_IMAGE_TO_IMAGE
    return MODE_REFERENCE_EDIT


def _role_phrase(reference: ReferenceImage) -> str:
    return ROLE_PHRASES.get(reference.effective_role, ROLE_PHRASES["reference"])


def _definition(reference: ReferenceImage, mode: str) -> str:
    description = reference.description.strip()
    observed = f" Visible details to use: {description}." if description else ""
    if mode == MODE_IMAGE_TO_IMAGE:
        return (
            f"{reference.mention} is the single source image and locked canvas. Preserve the same person, identity, "
            "pose, framing, background, lighting, clothing, and all other unmentioned details; change only what the "
            f"user explicitly requests.{observed}"
        )
    return (
        f"{reference.mention} defines {_role_phrase(reference)} only."
        f"{observed} Treat it as a reference input, not as an additional subject in the final image."
    )


def _retention(reference: ReferenceImage, mode: str) -> str:
    role = _role_phrase(reference)
    description = f" Specifically preserve {reference.description.strip()}." if reference.description.strip() else ""
    if mode == MODE_IMAGE_TO_IMAGE:
        return (
            f"{reference.mention}: fully_preserved - use it as the source image and preserve every unmentioned "
            f"visual property exactly; apply only the requested edit.{description}"
        )
    if reference.retention == "fully_preserved":
        action = f"retain {role} as faithfully as the new composition allows"
    elif reference.retention == "partially_preserved":
        action = f"retain the requested parts of {role} while allowing prompt-directed changes"
    elif reference.retention == "reference_only":
        action = f"use {role} only as guidance and do not copy unrelated details"
    else:
        action = f"transfer {role} to the target without copying unrelated reference content"
    return f"{reference.mention}: {reference.retention} - {action}.{description}"


def _reference_clause(references: Sequence[ReferenceImage], mode: str) -> str:
    if not references:
        return "No reference images are required; construct the scene entirely from the written direction."
    clauses = []
    for reference in references:
        if mode == MODE_IMAGE_TO_IMAGE:
            clauses.append(f"{reference.mention} is the locked source image; only the requested change is allowed")
        else:
            clauses.append(f"{reference.mention} supplies {_role_phrase(reference)} only")
    if len(clauses) == 1:
        return clauses[0] + "."
    return ", ".join(clauses[:-1]) + f", and {clauses[-1]}."


def _summary(prompt: str, references: Sequence[ReferenceImage], mode: str) -> str:
    compact = " ".join(prompt.split())
    if len(compact) > 560:
        compact = compact[:557].rstrip() + "..."
    mode_text = {
        MODE_TEXT_TO_IMAGE: "Create a new still image",
        MODE_IMAGE_TO_IMAGE: "Create a new still image guided by the source reference",
        MODE_REFERENCE_EDIT: "Create a new still image using the ordered reference set",
    }.get(mode, "Create a new still image")
    if not references:
        return f"[image generation] {mode_text}: {compact}.".strip()
    assignments = "; ".join(
        (
            f"{reference.mention} = locked source image, preserve everything except the explicit edit"
            if mode == MODE_IMAGE_TO_IMAGE
            else f"{reference.mention} = {_role_phrase(reference)}"
        )
        for reference in references
    )
    hard = " ".join(_hard_constraints(prompt))
    return (
        f"[image generation] {mode_text}: {compact}. "
        f"Reference assignments: {assignments}. Produce one coherent final image, not a reference sheet or collage. "
        f"{hard}"
    ).strip()


def _description(prompt: str, references: Sequence[ReferenceImage], state: StudioState) -> str:
    resolution = state.generation.resolution()
    adherence = state.prompt_options.adherence
    if adherence >= 0.9:
        adherence_text = "Treat the written request and explicit preservation instructions as strict constraints."
    elif adherence >= 0.65:
        adherence_text = "Preserve the written intent closely while resolving unspecified visual details coherently."
    else:
        adherence_text = "Use the request as the concept while allowing substantial visual interpretation."
    mode = resolve_mode(state.generation.mode, len(references))
    reference_text = "\n".join(
        (
            f"- {reference.mention}: locked FL2VA source image; preserve every unmentioned detail and perform only "
            "the explicit edit."
            if mode == MODE_IMAGE_TO_IMAGE
            else f"- {reference.mention}: use {_role_phrase(reference)} only; retention = {reference.retention}."
        )
        for reference in references
    ) or "- No reference images."
    hard_constraints = _hard_constraints(prompt)
    hard_text = (
        "\n".join(f"- {constraint}" for constraint in hard_constraints)
        if hard_constraints
        else "- Preserve every explicit user-requested action, edit, pose, gaze, direction, object and relationship."
    )
    return (
        f"Create one finished {resolution.aspect_ratio} {resolution.orientation} image at approximately "
        f"{resolution.actual_megapixels:.2f} megapixels ({resolution.width} × {resolution.height}).\n\n"
        f"Final-image instruction: {prompt}\n\n"
        f"Hard constraints (must be visibly satisfied):\n{hard_text}\n\n"
        f"Reference contract:\n{reference_text}\n\n"
        "Synthesis rule: render one finished scene containing only the subject(s) requested by the user. Reference "
        "images are source material, not extra people, cutouts, panels, mannequins, or objects to reproduce. Never "
        "emit a contact sheet, side-by-side comparison, collage, floating garment, duplicate body, or source-image "
        "background unless the user explicitly requests it. Apply only the assigned attributes from each image; do "
        "not let one reference overwrite unrelated identity, wardrobe, composition, style, or typography.\n\n"
        f"Production discipline: {adherence_text} Build a single internally consistent frame with deliberate subject "
        "placement, readable silhouette, coherent perspective, motivated lighting, controlled color relationships, "
        "credible material response and a clear visual hierarchy. Preserve any exact visible wording in quotation marks. "
        "Do not add signatures, watermarks, unexplained duplicate subjects or unrequested text."
    )


def _source_edit_text(prompt: str, source_ordinal: int = 1) -> str:
    """Remove a redundant source mention from a single-image edit command."""

    pattern = rf"(?<![\w@])@Image[_\s]*{int(source_ordinal)}\b"
    value = re.sub(pattern, "", prompt, flags=re.IGNORECASE)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    return _SPACE_RE.sub(" ", value).strip(" ,.;:-")


def _single_prompt(prompt: str, references: Sequence[ReferenceImage], mode: str) -> str:
    """Build a compact native-friendly instruction without section headings."""

    if mode == MODE_TEXT_TO_IMAGE:
        return (
            f"Generate one finished still image: {prompt}. Render one coherent frame with no collage, duplicate "
            "subjects, reference sheet, watermark, or unrequested text."
        )
    if mode == MODE_IMAGE_TO_IMAGE:
        source = references[0]
        edit = _source_edit_text(prompt, source.ordinal) or "apply the requested change"
        return (
            f"Edit {source.mention}, the single locked source image: {edit}. Preserve the same identity, face, hair "
            "except where explicitly changed, body, pose, clothing, framing, background, lighting, and every other "
            "unmentioned detail. Produce one edited image only; do not create a collage, duplicate person, cutout, "
            "reference sheet, or floating source elements."
        )

    assignments = "; ".join(
        f"{reference.mention} supplies {_role_phrase(reference)} only"
        for reference in references
    )
    return (
        f"Generate one coherent finished still image: {prompt}. Reference assignments: {assignments}. Combine the "
        "assigned attributes into the single requested subject and scene. The references are source material, not "
        "extra subjects: do not reproduce their panels, backgrounds, mannequins, cutouts, duplicate bodies, floating "
        "garments, or a reference sheet. Preserve identity and wardrobe as separately assigned."
    )


def _infer_retentions(
    references: Sequence[ReferenceImage],
    mode: str,
) -> tuple[ReferenceImage, ...]:
    """Resolve auto-managed retention from the operation and inferred role."""

    resolved: list[ReferenceImage] = []
    for reference in references:
        if "visually_analyzed" in reference.tags:
            resolved.append(reference)
            continue
        auto_managed = reference.retention_auto or reference.role_auto or reference.role == "auto"
        if not auto_managed:
            resolved.append(reference)
            continue
        if mode == MODE_IMAGE_TO_IMAGE or reference.effective_role in {"identity", "character", "face"}:
            retention = "fully_preserved"
        elif reference.effective_role in {"composition", "pose", "environment"}:
            retention = "partially_preserved"
        else:
            retention = "attribute_transfer"
        resolved.append(replace(reference, retention=retention, retention_auto=True))
    return tuple(resolved)


@dataclass(frozen=True, slots=True)
class CompileResult:
    sections: ImagePromptSections
    rendered: str
    native_prompt: str
    references: tuple[ReferenceImage, ...]
    resolved_mode: str
    diagnostics: tuple[Diagnostic, ...]

    def diagnostics_text(self) -> str:
        bag = DiagnosticBag(list(self.diagnostics))
        return bag.render()


class PromptCompiler:
    """Compile editor state into an inspectable H3 production brief."""

    def compile(self, state: StudioState, *, strict: bool = True) -> CompileResult:
        prompt = normalize_user_prompt(state.prompt)
        if not prompt:
            raise PromptFormatError("Prompt is empty.", hint="Describe the final still image before queuing the workflow.")

        bag = DiagnosticBag(list(state.diagnostics))
        bag.extend(validate_mentions(prompt, state.references).items)
        if strict and bag.has_errors:
            raise PromptFormatError(bag.render())

        references = state.enabled_references
        if state.prompt_options.infer_roles:
            references = infer_roles_from_prompt(prompt, references)
        resolved_mode = resolve_mode(state.generation.mode, len(references))
        references = _infer_retentions(references, resolved_mode)

        if resolved_mode == MODE_TEXT_TO_IMAGE and references:
            bag.warning(
                "references_ignored_in_t2i",
                "Text-to-image mode is explicit; connected image references will not be routed as REF2VA inputs.",
                field="mode",
            )
        if resolved_mode in {MODE_IMAGE_TO_IMAGE, MODE_REFERENCE_EDIT} and not references:
            raise PromptFormatError(
                f"{resolved_mode.replace('_', ' ').title()} requires at least one enabled reference image.",
                hint="Add an image card or switch Mode to Text to Image/Auto.",
            )

        mentioned = set(mention_ordinals(prompt))
        if references and not mentioned:
            bag.warning(
                "references_not_mentioned",
                "References are connected but the prompt does not explicitly mention them; role cards still guide compilation.",
                field="prompt",
                hint="Type @ to assign each image a precise job.",
            )

        definitions = "\n".join(_definition(reference, resolved_mode) for reference in references) or "N/A - no reference images."
        retention = "\n".join(_retention(reference, resolved_mode) for reference in references) or "N/A - no reference images."
        sections = ImagePromptSections(
            subject_definitions=definitions,
            summary=_summary(prompt, references, resolved_mode),
            retention_analysis=retention,
            detailed_description=_description(prompt, references, state),
        )
        rendered = sections.render()
        if state.prompt_options.enhance_mode == ENHANCE_OFF:
            native_prompt = compile_mentions(prompt, references)
        elif state.prompt_options.enhance_mode == ENHANCE_SINGLE:
            native_prompt = compile_mentions(_single_prompt(prompt, references, resolved_mode), references)
        else:
            native_prompt = compile_mentions(rendered, references)
        return CompileResult(sections, rendered, native_prompt, tuple(references), resolved_mode, tuple(bag.items))

    def accept_enhanced(self, value: str, base: CompileResult, *, strict: bool = True) -> CompileResult:
        """Validate VLM output and retain route/reference metadata from the base compile."""

        sections = ImagePromptSections.parse(value, strict=strict)
        rendered = sections.render()
        native_prompt = compile_mentions(rendered, base.references)
        return replace(base, sections=sections, rendered=rendered, native_prompt=native_prompt)
