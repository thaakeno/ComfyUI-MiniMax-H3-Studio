"""Domain-specific errors with messages suitable for ComfyUI's node panel."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


class H3StudioError(ValueError):
    """Base class for deterministic, user-correctable Studio errors."""

    code = "h3studio_error"

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message} Hint: {self.hint}" if self.hint else self.message


class StateDecodeError(H3StudioError):
    code = "state_decode_error"


class StateVersionError(H3StudioError):
    code = "state_version_error"


class ReferenceError(H3StudioError):
    code = "reference_error"


class MissingReferenceError(ReferenceError):
    code = "missing_reference"


class DuplicateReferenceError(ReferenceError):
    code = "duplicate_reference"


class PromptFormatError(H3StudioError):
    code = "prompt_format_error"


class ResolutionError(H3StudioError):
    code = "resolution_error"


class RouteError(H3StudioError):
    code = "route_error"


class OptionalDependencyError(H3StudioError):
    code = "optional_dependency_error"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A non-fatal problem that can travel through a Studio context."""

    level: str
    code: str
    message: str
    field: str | None = None
    reference_id: str | None = None
    hint: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = {"level": self.level, "code": self.code, "message": self.message}
        if self.field:
            payload["field"] = self.field
        if self.reference_id:
            payload["reference_id"] = self.reference_id
        if self.hint:
            payload["hint"] = self.hint
        return payload


@dataclass(slots=True)
class DiagnosticBag:
    """Mutable collector used while normalizing incomplete editor state."""

    items: list[Diagnostic] = field(default_factory=list)

    def add(
        self,
        level: str,
        code: str,
        message: str,
        *,
        field: str | None = None,
        reference_id: str | None = None,
        hint: str | None = None,
    ) -> None:
        self.items.append(Diagnostic(level, code, message, field, reference_id, hint))

    def warning(self, code: str, message: str, **kwargs: str) -> None:
        self.add("warning", code, message, **kwargs)

    def error(self, code: str, message: str, **kwargs: str) -> None:
        self.add("error", code, message, **kwargs)

    def extend(self, diagnostics: Iterable[Diagnostic]) -> None:
        self.items.extend(diagnostics)

    @property
    def has_errors(self) -> bool:
        return any(item.level == "error" for item in self.items)

    def render(self) -> str:
        if not self.items:
            return "No diagnostics."
        lines = []
        for item in self.items:
            location = f" [{item.field}]" if item.field else ""
            ref = f" ({item.reference_id})" if item.reference_id else ""
            hint = f" — {item.hint}" if item.hint else ""
            lines.append(f"{item.level.upper()} {item.code}{location}{ref}: {item.message}{hint}")
        return "\n".join(lines)
