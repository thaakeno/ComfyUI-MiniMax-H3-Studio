"""Versioned serialization contract shared by Python and the browser editor."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from .constants import (
    DEFAULT_HEIGHT,
    DEFAULT_MEGAPIXELS,
    DEFAULT_SEED,
    DEFAULT_WIDTH,
    ENHANCE_COMPILE,
    ENHANCE_MODES,
    MODE_AUTO,
    MODES,
    ROUTE_AUTO,
    ROUTES,
    SAMPLING_PROFILES,
    STATE_SCHEMA_VERSION,
)
from .errors import Diagnostic, DiagnosticBag, StateDecodeError, StateVersionError
from .references import ReferenceImage, normalize_references
from .resolution import ResolutionPlan, plan_resolution


def _choice(value: Any, choices: Sequence[str], fallback: str) -> str:
    text = str(value or fallback).strip().lower().replace(" ", "_").replace("-", "_")
    return text if text in choices else fallback


def _float(value: Any, fallback: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return min(maximum, max(minimum, parsed))


def _int(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return min(maximum, max(minimum, parsed))


@dataclass(frozen=True, slots=True)
class PromptOptions:
    enhance_mode: str = ENHANCE_COMPILE
    adherence: float = 0.85
    detail_level: str = "detailed"
    preserve_user_text: bool = True
    infer_roles: bool = True
    system_instruction: str = ""
    analyzer_model: str = ""
    analyzer_device: str = "auto"
    analyzer_quantization: str = "auto"
    analyzer_max_tokens: int = 1800
    analyzer_keep_loaded: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "enhance_mode": self.enhance_mode,
            "adherence": self.adherence,
            "detail_level": self.detail_level,
            "preserve_user_text": self.preserve_user_text,
            "infer_roles": self.infer_roles,
            "system_instruction": self.system_instruction,
            "analyzer_model": self.analyzer_model,
            "analyzer_device": self.analyzer_device,
            "analyzer_quantization": self.analyzer_quantization,
            "analyzer_max_tokens": self.analyzer_max_tokens,
            "analyzer_keep_loaded": self.analyzer_keep_loaded,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> PromptOptions:
        value = value or {}
        detail = str(value.get("detail_level") or "detailed").strip().lower()
        if detail not in {"concise", "detailed", "maximum"}:
            detail = "detailed"
        return cls(
            enhance_mode=_choice(value.get("enhance_mode"), ENHANCE_MODES, ENHANCE_COMPILE),
            adherence=_float(value.get("adherence"), 0.85, 0.0, 1.0),
            detail_level=detail,
            preserve_user_text=bool(value.get("preserve_user_text", True)),
            infer_roles=bool(value.get("infer_roles", True)),
            system_instruction=str(value.get("system_instruction") or "").strip(),
            analyzer_model=str(value.get("analyzer_model") or "").strip(),
            analyzer_device=str(value.get("analyzer_device") or "auto").strip().lower(),
            analyzer_quantization=str(value.get("analyzer_quantization") or "auto").strip().lower(),
            analyzer_max_tokens=_int(value.get("analyzer_max_tokens"), 1800, 128, 8192),
            analyzer_keep_loaded=bool(value.get("analyzer_keep_loaded", False)),
        )


@dataclass(frozen=True, slots=True)
class GenerationOptions:
    mode: str = MODE_AUTO
    route: str = ROUTE_AUTO
    seed: int = DEFAULT_SEED
    aspect_ratio: str = "1:1"
    megapixels: float = DEFAULT_MEGAPIXELS
    custom_width: int = DEFAULT_WIDTH
    custom_height: int = DEFAULT_HEIGHT
    cap_native_resolution: bool = True
    sampling_profile: str = "base_quality_20"
    frame_profile: str = "recommended_5"
    frame_selection: str = "decode_recommended"
    reference_short_edge: int = 2048
    source_image_ordinal: int = 1

    def resolution(self) -> ResolutionPlan:
        return plan_resolution(
            self.aspect_ratio,
            self.megapixels,
            custom_width=self.custom_width,
            custom_height=self.custom_height,
            cap_native=self.cap_native_resolution,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "route": self.route,
            "seed": self.seed,
            "aspect_ratio": self.aspect_ratio,
            "megapixels": self.megapixels,
            "custom_width": self.custom_width,
            "custom_height": self.custom_height,
            "cap_native_resolution": self.cap_native_resolution,
            "sampling_profile": self.sampling_profile,
            "frame_profile": self.frame_profile,
            "frame_selection": self.frame_selection,
            "reference_short_edge": self.reference_short_edge,
            "source_image_ordinal": self.source_image_ordinal,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> GenerationOptions:
        value = value or {}
        sampling = str(value.get("sampling_profile") or "base_quality_20")
        sampling = {
            "turbo_er_sde_6": "lightx_er_sde_4",
            "turbo_sa_solver_4": "lightx_sa_solver_4",
        }.get(sampling, sampling)
        if sampling not in SAMPLING_PROFILES:
            sampling = "base_quality_20"
        frame_profile = str(value.get("frame_profile") or "recommended_5")
        if frame_profile not in {"recommended_5", "balanced_9", "quality_13", "maximum_20"}:
            frame_profile = "recommended_5"
        frame_selection = str(value.get("frame_selection") or "decode_recommended")
        if frame_selection not in {"decode_recommended", "first", "middle", "last", "automatic_quality", "fixed"}:
            frame_selection = "decode_recommended"
        return cls(
            mode=_choice(value.get("mode"), MODES, MODE_AUTO),
            route=_choice(value.get("route"), ROUTES, ROUTE_AUTO),
            seed=_int(value.get("seed"), DEFAULT_SEED, 0, 2**63 - 1),
            aspect_ratio=str(value.get("aspect_ratio") or "1:1"),
            megapixels=_float(value.get("megapixels"), DEFAULT_MEGAPIXELS, 0.20, 2.00),
            custom_width=_int(value.get("custom_width"), DEFAULT_WIDTH, 32, 16384),
            custom_height=_int(value.get("custom_height"), DEFAULT_HEIGHT, 32, 16384),
            cap_native_resolution=bool(value.get("cap_native_resolution", True)),
            sampling_profile=sampling,
            frame_profile=frame_profile,
            frame_selection=frame_selection,
            reference_short_edge=_int(value.get("reference_short_edge"), 2048, 256, 4096),
            source_image_ordinal=_int(value.get("source_image_ordinal"), 1, 1, 9),
        )


@dataclass(frozen=True, slots=True)
class StudioState:
    """Canonical state emitted by the H3 Studio Director frontend."""

    schema_version: int = STATE_SCHEMA_VERSION
    prompt: str = ""
    references: tuple[ReferenceImage, ...] = field(default_factory=tuple)
    prompt_options: PromptOptions = field(default_factory=PromptOptions)
    generation: GenerationOptions = field(default_factory=GenerationOptions)
    ui: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)

    @property
    def enabled_references(self) -> tuple[ReferenceImage, ...]:
        return tuple(reference for reference in self.references if reference.enabled)

    @property
    def reference_count(self) -> int:
        return len(self.enabled_references)

    def with_prompt(self, prompt: str) -> StudioState:
        return replace(self, prompt=str(prompt or ""))

    def with_references(self, references: Sequence[ReferenceImage]) -> StudioState:
        return replace(self, references=normalize_references(references))

    def as_dict(self, *, include_diagnostics: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "prompt": self.prompt,
            "references": [reference.as_dict() for reference in self.references],
            "prompt_options": self.prompt_options.as_dict(),
            "generation": self.generation.as_dict(),
            "ui": dict(self.ui),
        }
        if include_diagnostics:
            payload["diagnostics"] = [diagnostic.as_dict() for diagnostic in self.diagnostics]
        return payload

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(
            self.as_dict(),
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
            sort_keys=pretty,
        )

    @classmethod
    def from_json(cls, value: str | bytes | None, *, strict: bool = False) -> StudioState:
        if not value:
            return cls()
        try:
            decoded = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise StateDecodeError(
                "The H3 Studio state payload is not valid JSON.",
                hint="Recreate the Director node or restore a known-good workflow checkpoint.",
            ) from exc
        if not isinstance(decoded, Mapping):
            raise StateDecodeError("The H3 Studio state payload must be a JSON object.")
        return cls.from_dict(decoded, strict=strict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, strict: bool = False) -> StudioState:
        migrated = migrate_state_dict(value)
        version = _int(migrated.get("schema_version"), STATE_SCHEMA_VERSION, 1, 999)
        if version > STATE_SCHEMA_VERSION:
            raise StateVersionError(
                f"This workflow uses H3 Studio state schema {version}, but this extension supports {STATE_SCHEMA_VERSION}.",
                hint="Update ComfyUI-MiniMax-H3-Studio before running the workflow.",
            )
        bag = DiagnosticBag()
        raw_references = migrated.get("references") or ()
        if not isinstance(raw_references, Sequence) or isinstance(raw_references, (str, bytes)):
            raw_references = ()
            bag.warning("invalid_references", "The serialized reference list was invalid and has been cleared.")
        references = normalize_references(raw_references, diagnostics=bag, strict=strict)
        diagnostics = tuple(bag.items)
        return cls(
            schema_version=STATE_SCHEMA_VERSION,
            prompt=str(migrated.get("prompt") or ""),
            references=references,
            prompt_options=PromptOptions.from_dict(_mapping(migrated.get("prompt_options"))),
            generation=GenerationOptions.from_dict(_mapping(migrated.get("generation"))),
            ui=dict(_mapping(migrated.get("ui"))),
            diagnostics=diagnostics,
        )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def migrate_state_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    """Upgrade previous private prototypes without mutating the source object."""

    migrated = dict(value)
    version = _int(migrated.get("schema_version"), 1, 1, 999)
    if version == 1:
        settings = dict(_mapping(migrated.pop("settings", {})))
        generation = dict(_mapping(migrated.get("generation")))
        prompt_options = dict(_mapping(migrated.get("prompt_options")))
        for key in (
            "mode",
            "route",
            "seed",
            "aspect_ratio",
            "megapixels",
            "custom_width",
            "custom_height",
            "sampling_profile",
        ):
            if key in settings and key not in generation:
                generation[key] = settings[key]
        for key in ("enhance_mode", "adherence", "detail_level", "analyzer_model"):
            if key in settings and key not in prompt_options:
                prompt_options[key] = settings[key]
        migrated["generation"] = generation
        migrated["prompt_options"] = prompt_options
        migrated["schema_version"] = 2
        version = 2
    if version == 2:
        # Schema 3 adds an optional storage_name to references uploaded inside
        # the Director. Existing link-backed references need no transformation.
        migrated["schema_version"] = 3
    return migrated
