"""Readable, tensor-free execution reports for the ComfyUI console."""

from __future__ import annotations

from textwrap import indent

from .constants import VERSION
from .context import H3StudioContext


def _block(value: str) -> str:
    text = str(value or "").strip() or "(empty)"
    return indent(text, "  ")


def format_execution_report(context: H3StudioContext, enhancement_note: str = "") -> str:
    state = context.state
    generation = state.generation
    prompt_options = state.prompt_options
    resolution = context.resolution
    references = context.compile_result.references
    if not prompt_options.analyze_images:
        analysis_status = "off"
    elif prompt_options.analyzer_resolution == 0:
        analysis_status = "on at native reference resolution"
    else:
        analysis_status = f"on at {prompt_options.analyzer_resolution}px max edge"
    lines = [
        "=" * 72,
        f"H3 STUDIO EXECUTION - v{VERSION}",
        "=" * 72,
        f"Mode          : {context.compile_result.resolved_mode}",
        f"Route         : {context.route.requested} -> {context.route.selected}",
        f"Route reason  : {context.route.reason}",
        f"Canvas        : {resolution.width} x {resolution.height} | {resolution.actual_megapixels:.2f} MP",
        f"Target        : {generation.megapixels:.2f} MP | aspect {generation.aspect_ratio}",
        f"Seed          : {generation.seed}",
        f"Sampling      : {generation.sampling_profile}",
        f"Frames        : {generation.frame_profile}",
        f"Prompt shaping: {prompt_options.enhance_mode} | image analysis {analysis_status} "
        f"| detailed second pass {'on' if prompt_options.deep_enhancement else 'off'} "
        f"| reference priority {prompt_options.adherence:.0%}",
        f"References    : {len(references)}",
    ]
    if references:
        for reference in references:
            description = f" | {reference.description.strip()}" if reference.description.strip() else ""
            role_source = "auto" if reference.role_auto else "manual"
            retention_source = "auto" if reference.retention_auto else "manual"
            lines.append(
                f"  @Image {reference.ordinal}: {reference.display_name} | role={reference.effective_role} | "
                f"retention={reference.retention} | set_by=role:{role_source},retention:{retention_source}{description}"
            )
    if enhancement_note.strip():
        lines.extend(["", "Enhancement note:", _block(enhancement_note)])
    lines.extend(
        [
            "",
            "Original prompt:",
            _block(state.prompt),
            "",
            "Compiled H3 prompt:",
            _block(context.compile_result.native_prompt),
            "",
            "Diagnostics:",
            _block(context.compile_result.diagnostics_text()),
            "=" * 72,
        ]
    )
    return "\n".join(lines)
