"""Deterministic four-section compiler used with or without a VLM."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from ..constants import MODE_AUTO, MODE_IMAGE_TO_IMAGE, MODE_REFERENCE_EDIT, MODE_TEXT_TO_IMAGE
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
_LEGACY_RUNTIME_REF_RE = re.compile(r"__H3STUDIO_REF_([1-9]\d*)__", re.IGNORECASE)


def normalize_user_prompt(value: str) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _INVISIBLE_RE.sub("", text)
    text = _LEGACY_RUNTIME_REF_RE.sub(lambda match: f"@Image {match.group(1)}", text)
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


def _definition(reference: ReferenceImage) -> str:
    description = reference.description.strip()
    observed = f" The supplied analysis describes: {description}." if description else ""
    return (
        f"{reference.subject_tag} from {reference.picture_tag} defines {_role_phrase(reference)}."
        f"{observed} Track this reference consistently wherever its role is requested."
    )


def _retention(reference: ReferenceImage) -> str:
    role = _role_phrase(reference)
    description = f" Specifically preserve {reference.description.strip()}." if reference.description.strip() else ""
    if reference.retention == "fully_preserved":
        action = f"retain {role} as faithfully as the new composition allows"
    elif reference.retention == "partially_preserved":
        action = f"retain the requested parts of {role} while allowing prompt-directed changes"
    elif reference.retention == "reference_only":
        action = f"use {role} only as guidance and do not copy unrelated details"
    else:
        action = f"transfer {role} to the target without copying unrelated reference content"
    return f"{reference.subject_tag}: {reference.retention} - {action}.{description}"


def _reference_clause(references: Sequence[ReferenceImage]) -> str:
    if not references:
        return "No reference images are required; construct the scene entirely from the written direction."
    clauses = []
    for reference in references:
        clauses.append(f"{reference.subject_tag} supplies {_role_phrase(reference)}")
    if len(clauses) == 1:
        return clauses[0] + "."
    return ", ".join(clauses[:-1]) + f", and {clauses[-1]}."


def _summary(prompt: str, references: Sequence[ReferenceImage], mode: str) -> str:
    compact = " ".join(prompt.split())
    if len(compact) > 560:
        compact = compact[:557].rstrip() + "..."
    relationship = _reference_clause(references)
    mode_text = {
        MODE_TEXT_TO_IMAGE: "Create a new still image",
        MODE_IMAGE_TO_IMAGE: "Create a new still image guided by the source reference",
        MODE_REFERENCE_EDIT: "Create a new still image using the ordered reference set",
    }.get(mode, "Create a new still image")
    return f"[image generation] {mode_text}: {compact} {relationship}".strip()


def _description(prompt: str, references: Sequence[ReferenceImage], state: StudioState) -> str:
    resolution = state.generation.resolution()
    adherence = state.prompt_options.adherence
    if adherence >= 0.9:
        adherence_text = "Treat the written request and explicit preservation instructions as strict constraints."
    elif adherence >= 0.65:
        adherence_text = "Preserve the written intent closely while resolving unspecified visual details coherently."
    else:
        adherence_text = "Use the request as the concept while allowing substantial visual interpretation."
    reference_text = _reference_clause(references)
    return (
        f"Create one finished {resolution.aspect_ratio} {resolution.orientation} image at approximately "
        f"{resolution.actual_megapixels:.2f} megapixels ({resolution.width} × {resolution.height}).\n\n"
        f"Core direction: {prompt}\n\n"
        f"Reference direction: {reference_text} Apply only the attributes assigned to each reference; do not allow "
        "one image to overwrite unrelated identity, wardrobe, composition, style or typography from another.\n\n"
        f"Production discipline: {adherence_text} Build a single internally consistent frame with deliberate subject "
        "placement, readable silhouette, coherent perspective, motivated lighting, controlled color relationships, "
        "credible material response and a clear visual hierarchy. Preserve any exact visible wording in quotation marks. "
        "Do not add signatures, watermarks, unexplained duplicate subjects or unrequested text."
    )


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

        definitions = "\n".join(_definition(reference) for reference in references) or "N/A - no reference images."
        retention = "\n".join(_retention(reference) for reference in references) or "N/A - no reference images."
        sections = ImagePromptSections(
            subject_definitions=definitions,
            summary=_summary(prompt, references, resolved_mode),
            retention_analysis=retention,
            detailed_description=_description(prompt, references, state),
        )
        rendered = sections.render()
        native_prompt = compile_mentions(rendered, references)
        return CompileResult(sections, rendered, native_prompt, tuple(references), resolved_mode, tuple(bag.items))

    def accept_enhanced(self, value: str, base: CompileResult, *, strict: bool = True) -> CompileResult:
        """Validate VLM output and retain route/reference metadata from the base compile."""

        sections = ImagePromptSections.parse(value, strict=strict)
        rendered = sections.render()
        native_prompt = compile_mentions(rendered, base.references)
        return replace(base, sections=sections, rendered=rendered, native_prompt=native_prompt)
