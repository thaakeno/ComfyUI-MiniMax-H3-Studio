"""PNG saving that preserves the completed H3 Studio project state."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:  # ComfyUI supplies this module at runtime; pure tests exercise the helpers.
    import nodes as comfy_nodes
except ImportError:  # pragma: no cover - only used outside ComfyUI
    comfy_nodes = None

from ..context import H3StudioContext
from ..telemetry import record_generation_success


def _saved_image_count(images: Any) -> int:
    shape = getattr(images, "shape", ())
    if shape and int(shape[0]) > 0:
        return int(shape[0])
    try:
        return max(1, len(images))
    except (TypeError, AttributeError):
        return 1


def _director_nodes(workflow: dict[str, Any]):
    for node in workflow.get("nodes", ()):
        if node.get("type") == "H3StudioDirector":
            yield node
    for subgraph in workflow.get("definitions", {}).get("subgraphs", ()):
        yield from _director_nodes(subgraph)


def _replace_director_state(workflow: dict[str, Any], state_json: str) -> None:
    for director in _director_nodes(workflow):
        director.setdefault("properties", {})["h3studio_state"] = state_json
        state_index = next(
            (
                index
                for index, input_slot in enumerate(director.get("inputs", ()))
                if input_slot.get("name") == "studio_state"
            ),
            None,
        )
        values = director.get("widgets_values")
        if state_index is not None and isinstance(values, list) and state_index < len(values):
            values[state_index] = state_json


def completed_png_metadata(
    prompt: dict[str, Any] | None,
    extra_pnginfo: dict[str, Any] | None,
    context: H3StudioContext,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return metadata copies containing the state that actually generated the PNG."""

    if not isinstance(context, H3StudioContext):
        raise ValueError("Connect H3 Studio Director's studio_context output to the final save node.")
    state_json = context.state.to_json()
    saved_prompt = deepcopy(prompt) if prompt is not None else None
    saved_extra = deepcopy(extra_pnginfo) if extra_pnginfo is not None else {}
    workflow = saved_extra.get("workflow")
    if isinstance(workflow, dict):
        _replace_director_state(workflow, state_json)
    if isinstance(saved_prompt, dict):
        for prompt_node in saved_prompt.values():
            if prompt_node.get("class_type") == "H3StudioDirector":
                prompt_node.setdefault("inputs", {})["studio_state"] = state_json
    saved_extra["h3studio"] = {
        "schema_version": context.schema_version,
        "state": context.state.as_dict(),
        "compiled_prompt": context.prompt,
        "resolved_mode": context.compile_result.resolved_mode,
        "resolved_route": context.route.selected,
        "width": context.width,
        "height": context.height,
        "seed": context.seed,
        "sampling_profile": context.state.generation.sampling_profile,
        "reference_storage": [reference.storage_name for reference in context.state.references],
        "portability": "same_machine_storage_references",
    }
    return saved_prompt, saved_extra


_SaveImageBase = comfy_nodes.SaveImage if comfy_nodes is not None else object


class H3StudioSaveImage(_SaveImageBase):
    """Native ComfyUI PNG saving plus completed H3 Studio generation metadata."""

    CATEGORY = "H3 Studio"
    DESCRIPTION = "Save the final still with restorable completed H3 Studio workflow metadata."

    @classmethod
    def INPUT_TYPES(cls):
        if comfy_nodes is None:  # pragma: no cover - ComfyUI runtime guard
            return {}
        inputs = deepcopy(comfy_nodes.SaveImage.INPUT_TYPES())
        inputs["required"]["studio_context"] = ("H3_STUDIO_CONTEXT",)
        return inputs

    def save_images(
        self,
        images,
        studio_context,
        filename_prefix="H3Studio",
        prompt=None,
        extra_pnginfo=None,
    ):
        saved_prompt, saved_extra = completed_png_metadata(prompt, extra_pnginfo, studio_context)
        result = super().save_images(images, filename_prefix, saved_prompt, saved_extra)
        # Count only after ComfyUI has actually completed every requested save.
        # The reporter accepts an integer only and performs network work later.
        record_generation_success(_saved_image_count(images))
        return result


NODE_CLASS_MAPPINGS = {"H3StudioSaveImage": H3StudioSaveImage}
NODE_DISPLAY_NAME_MAPPINGS = {"H3StudioSaveImage": "H3 Studio · Save Restorable PNG"}
