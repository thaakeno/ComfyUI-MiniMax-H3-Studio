"""Four-section image prompt representation.

MiniMax's reference-video guide contains six sections. H3 Studio intentionally
uses only the four visual sections for still generation; audio sections are not
emitted as empty placeholders.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from ..constants import PROMPT_SECTION_NAMES
from ..errors import PromptFormatError

_SECTION_RE = re.compile(
    r"(?im)^(subject_definitions|summary|retention_analysis|detailed_description)\s*:\s*",
)


def _clean_body(value: str) -> str:
    lines = [line.rstrip() for line in str(value or "").strip().splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ImagePromptSections:
    subject_definitions: str
    summary: str
    retention_analysis: str
    detailed_description: str

    def as_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in PROMPT_SECTION_NAMES}

    def render(self) -> str:
        chunks = []
        for name in PROMPT_SECTION_NAMES:
            chunks.append(f"{name}:\n{_clean_body(getattr(self, name))}")
        return "\n\n".join(chunks).rstrip() + "\n"

    def validate(self) -> tuple[str, ...]:
        issues = []
        for name in PROMPT_SECTION_NAMES:
            if not _clean_body(getattr(self, name)):
                issues.append(f"{name} is empty")
        combined = self.render().lower()
        if "overall_soundscape:" in combined or "non_diegetic_music:" in combined:
            issues.append("image prompt contains video-only audio sections")
        return tuple(issues)

    @classmethod
    def from_mapping(cls, value: Mapping[str, str]) -> ImagePromptSections:
        return cls(**{name: _clean_body(value.get(name, "")) for name in PROMPT_SECTION_NAMES})

    @classmethod
    def parse(cls, value: str, *, strict: bool = True) -> ImagePromptSections:
        text = str(value or "").strip()
        matches = list(_SECTION_RE.finditer(text))
        if not matches:
            raise PromptFormatError("Enhanced prompt does not contain the required image sections.")
        bodies: dict[str, str] = {}
        for index, match in enumerate(matches):
            name = match.group(1).lower()
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            if name in bodies and strict:
                raise PromptFormatError(f"Enhanced prompt contains duplicate {name} sections.")
            bodies[name] = _clean_body(text[start:end])
        missing = [name for name in PROMPT_SECTION_NAMES if name not in bodies]
        if missing and strict:
            raise PromptFormatError(f"Enhanced prompt is missing: {', '.join(missing)}.")
        sections = cls.from_mapping(bodies)
        if strict:
            issues = sections.validate()
            if issues:
                raise PromptFormatError("; ".join(issues))
        return sections
