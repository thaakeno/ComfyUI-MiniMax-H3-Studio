"""Ordered image references and the friendly ``@Image N`` language."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath
from typing import Any

from .constants import MAX_REFERENCE_IMAGES, REFERENCE_ROLES, RETENTION_MARKERS, ROLE_KEYWORDS
from .errors import DiagnosticBag, DuplicateReferenceError, MissingReferenceError, ReferenceError

_MENTION_RE = re.compile(r"(?<![\w@])@Image\s*([1-9]\d*)\b", re.IGNORECASE)
_PICTURE_RE = re.compile(r"<Picture\s+([1-9]\d*)>", re.IGNORECASE)
_SUBJECT_RE = re.compile(r"<Subject\s+([1-9]\d*)>", re.IGNORECASE)
_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def new_reference_id() -> str:
    return f"ref_{uuid.uuid4().hex[:12]}"


def clean_filename(value: str) -> str:
    """Return a display-safe basename without trusting client path separators."""

    normalized = str(value or "").replace("\\", "/").strip()
    return PurePosixPath(normalized).name[:240]


def clean_storage_name(value: str) -> str:
    """Normalize a ComfyUI input-relative filename without allowing traversal."""

    normalized = str(value or "").replace("\\", "/").strip()
    annotation = ""
    for suffix in (" [input]", " [output]", " [temp]"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
            annotation = suffix
            break
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        return ""
    safe = "/".join(part for part in path.parts if part not in {"", "."})[:500]
    return f"{safe}{annotation}" if safe else ""


def stable_reference_id(filename: str, ordinal: int) -> str:
    stem = PurePosixPath(clean_filename(filename)).stem or f"image_{ordinal}"
    stem = _SAFE_ID_RE.sub("-", stem).strip("-").lower()[:40] or f"image-{ordinal}"
    return f"ref_{ordinal}_{stem}"


def canonical_role(value: str | None) -> str:
    role = str(value or "auto").strip().lower().replace(" ", "_").replace("-", "_")
    return role if role in REFERENCE_ROLES else "auto"


def canonical_retention(value: str | None) -> str:
    marker = str(value or "attribute_transfer").strip().lower().replace(" ", "_").replace("-", "_")
    return marker if marker in RETENTION_MARKERS else "attribute_transfer"


@dataclass(frozen=True, slots=True)
class ReferenceImage:
    """Serializable metadata for one ordered image input.

    Tensor values are intentionally not stored here. ComfyUI links carry tensors;
    the state payload carries identity, labels and user intent.
    """

    id: str
    filename: str
    ordinal: int
    storage_name: str | None = None
    role: str = "auto"
    retention: str = "attribute_transfer"
    description: str = ""
    enabled: bool = True
    source_node_id: str | None = None
    source_slot: int = 0
    width: int | None = None
    height: int | None = None
    fingerprint: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def mention(self) -> str:
        return f"@Image {self.ordinal}"

    @property
    def picture_tag(self) -> str:
        return f"<Picture {self.ordinal}>"

    @property
    def subject_tag(self) -> str:
        return f"<Subject {self.ordinal}>"

    @property
    def display_name(self) -> str:
        return clean_filename(self.filename) or f"Image {self.ordinal}"

    @property
    def effective_role(self) -> str:
        return self.role if self.role != "auto" else "reference"

    def with_ordinal(self, ordinal: int) -> ReferenceImage:
        return replace(self, ordinal=ordinal)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "filename": self.filename,
            "ordinal": self.ordinal,
            "role": self.role,
            "retention": self.retention,
            "description": self.description,
            "enabled": self.enabled,
            "source_slot": self.source_slot,
            "tags": list(self.tags),
        }
        if self.storage_name:
            payload["storage_name"] = self.storage_name
        for key in ("source_node_id", "width", "height", "fingerprint"):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], fallback_ordinal: int) -> ReferenceImage:
        ordinal = _positive_int(value.get("ordinal"), fallback_ordinal)
        storage_name = clean_storage_name(str(value.get("storage_name") or ""))
        filename = clean_filename(
            str(value.get("filename") or value.get("name") or storage_name or f"image_{ordinal}.png")
        )
        raw_tags = value.get("tags") or ()
        tags = tuple(str(item).strip() for item in raw_tags if str(item).strip()) if isinstance(raw_tags, Sequence) else ()
        return cls(
            id=str(value.get("id") or stable_reference_id(filename, ordinal)),
            filename=filename,
            ordinal=ordinal,
            storage_name=storage_name or None,
            role=canonical_role(value.get("role")),
            retention=canonical_retention(value.get("retention")),
            description=str(value.get("description") or "").strip(),
            enabled=bool(value.get("enabled", True)),
            source_node_id=_optional_string(value.get("source_node_id")),
            source_slot=_nonnegative_int(value.get("source_slot"), 0),
            width=_optional_positive_int(value.get("width")),
            height=_optional_positive_int(value.get("height")),
            fingerprint=_optional_string(value.get("fingerprint")),
            tags=tags,
        )


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _nonnegative_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed >= 0 else fallback


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


@dataclass(frozen=True, slots=True)
class Mention:
    ordinal: int
    start: int
    end: int
    source: str

    @property
    def token(self) -> str:
        return f"@Image {self.ordinal}"


def iter_mentions(prompt: str) -> Iterator[Mention]:
    for match in _MENTION_RE.finditer(prompt or ""):
        yield Mention(int(match.group(1)), match.start(), match.end(), match.group(0))


def mention_ordinals(prompt: str, *, unique: bool = True) -> list[int]:
    values = [mention.ordinal for mention in iter_mentions(prompt)]
    if not unique:
        return values
    result: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def native_reference_ordinals(prompt: str) -> list[int]:
    matches = list(_PICTURE_RE.finditer(prompt or "")) + list(_SUBJECT_RE.finditer(prompt or ""))
    return sorted({int(match.group(1)) for match in matches})


def rewrite_mentions(prompt: str, ordinal_map: Mapping[int, int]) -> str:
    """Rewrite mentions after a reorder while leaving unrelated text intact."""

    def substitute(match: re.Match[str]) -> str:
        old = int(match.group(1))
        new = ordinal_map.get(old, old)
        return f"@Image {new}"

    return _MENTION_RE.sub(substitute, prompt or "")


def compile_mentions(prompt: str, references: Sequence[ReferenceImage], *, tag: str = "picture") -> str:
    """Compile friendly mentions to the ordered H3 token language."""

    by_ordinal = {reference.ordinal: reference for reference in references if reference.enabled}
    missing = [ordinal for ordinal in mention_ordinals(prompt) if ordinal not in by_ordinal]
    if missing:
        joined = ", ".join(f"@Image {ordinal}" for ordinal in missing)
        raise MissingReferenceError(
            f"Prompt references {joined}, but those image slots are not connected.",
            hint="Reconnect the images, reorder the cards, or remove the stale mentions.",
        )

    def substitute(match: re.Match[str]) -> str:
        reference = by_ordinal[int(match.group(1))]
        return reference.subject_tag if tag == "subject" else reference.picture_tag

    return _MENTION_RE.sub(substitute, prompt or "")


def normalize_references(
    values: Iterable[ReferenceImage | Mapping[str, Any]],
    *,
    diagnostics: DiagnosticBag | None = None,
    strict: bool = False,
) -> tuple[ReferenceImage, ...]:
    """Validate, deduplicate and renumber a reference collection."""

    bag = diagnostics or DiagnosticBag()
    parsed: list[ReferenceImage] = []
    seen_ids: set[str] = set()
    for fallback_ordinal, value in enumerate(values, start=1):
        reference = value if isinstance(value, ReferenceImage) else ReferenceImage.from_dict(value, fallback_ordinal)
        if reference.id in seen_ids:
            message = f"Reference id {reference.id!r} occurs more than once."
            if strict:
                raise DuplicateReferenceError(message)
            bag.warning("duplicate_reference_id", message, reference_id=reference.id)
            reference = replace(reference, id=f"{reference.id}_{fallback_ordinal}")
        seen_ids.add(reference.id)
        parsed.append(reference)

    if len(parsed) > MAX_REFERENCE_IMAGES:
        message = f"H3 supports at most {MAX_REFERENCE_IMAGES} reference images; {len(parsed)} were supplied."
        if strict:
            raise ReferenceError(message)
        bag.warning("too_many_references", message, hint="Only the first nine enabled images will be used.")
        parsed = parsed[:MAX_REFERENCE_IMAGES]

    return tuple(reference.with_ordinal(index) for index, reference in enumerate(parsed, start=1))


def infer_role(context: str, *, fallback: str = "auto") -> str:
    """Infer a conservative role from nearby user language.

    This is deliberately a fallback, not a claim that the image was analyzed.
    A VLM description or an explicit card role always has priority.
    """

    lowered = f" {str(context or '').lower()} "
    scored: list[tuple[int, int, str]] = []
    for order, (role, keywords) in enumerate(ROLE_KEYWORDS.items()):
        score = sum(2 if f" {keyword} " in lowered else 1 for keyword in keywords if keyword in lowered)
        if score:
            scored.append((score, -order, role))
    return max(scored)[2] if scored else canonical_role(fallback)


def infer_roles_from_prompt(prompt: str, references: Sequence[ReferenceImage], window: int = 120) -> tuple[ReferenceImage, ...]:
    mentions = list(iter_mentions(prompt))
    inferred: list[ReferenceImage] = []
    for reference in references:
        if reference.role != "auto":
            inferred.append(reference)
            continue
        matching = [mention for mention in mentions if mention.ordinal == reference.ordinal]
        snippets = []
        for mention in matching:
            # Prefer the sentence containing the mention. A broad symmetric
            # window frequently leaks the role assigned to the next image.
            left_candidates = [prompt.rfind(mark, max(0, mention.start - window), mention.start) for mark in ".!?\n;"]
            right_candidates = [prompt.find(mark, mention.end, min(len(prompt), mention.end + window)) for mark in ".!?\n;"]
            left = max(left_candidates) + 1
            valid_right = [candidate for candidate in right_candidates if candidate >= 0]
            right = min(valid_right) + 1 if valid_right else min(len(prompt), mention.end + window)
            snippets.append(prompt[left:right])
        role = infer_role(" ".join(snippets), fallback="auto")
        inferred.append(replace(reference, role=role))
    return tuple(inferred)


def validate_mentions(prompt: str, references: Sequence[ReferenceImage]) -> DiagnosticBag:
    bag = DiagnosticBag()
    enabled = {reference.ordinal for reference in references if reference.enabled}
    for ordinal in mention_ordinals(prompt):
        if ordinal not in enabled:
            bag.error(
                "missing_reference",
                f"@Image {ordinal} has no enabled image card.",
                field="prompt",
                reference_id=f"image_{ordinal}",
                hint="Reconnect the image or remove the mention.",
            )
    for ordinal in native_reference_ordinals(prompt):
        if ordinal not in enabled:
            bag.warning(
                "native_reference_without_card",
                f"Native reference tag {ordinal} has no matching image card.",
                field="prompt",
            )
    return bag
