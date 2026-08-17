"""PNG saving that preserves the completed H3 Studio project state."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:  # ComfyUI supplies this module at runtime; pure tests exercise the helpers.
    import nodes as comfy_nodes
except ImportError:  # pragma: no cover - only used outside ComfyUI
    comfy_nodes = None

from ..context import H3StudioContext


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


def _director_widget_index(director: dict[str, Any], name: str) -> int | None:
    """Resolve a serialized widget index without assuming every input owns a widget."""

    inputs = director.get("inputs", ())
    widget_index = 0
    for input_index, input_slot in enumerate(inputs):
        if input_slot.get("widget") is not None:
            if input_slot.get("name") == name:
                return widget_index
            widget_index += 1
        elif input_slot.get("name") == name:
            # Minimal/legacy workflow fixtures may omit the widget descriptor.
            values = director.get("widgets_values")
            if isinstance(values, list) and input_index < len(values):
                return input_index
    return None


def _set_director_widget(director: dict[str, Any], name: str, value: Any) -> None:
    index = _director_widget_index(director, name)
    values = director.get("widgets_values")
    if index is not None and isinstance(values, list) and index < len(values):
        values[index] = value


def _replace_director_state(workflow: dict[str, Any], state_json: str, seed: int) -> None:
    for director in _director_nodes(workflow):
        director.setdefault("properties", {})["h3studio_state"] = state_json
        _set_director_widget(director, "studio_state", state_json)
        _set_director_widget(director, "seed", int(seed))


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
        _replace_director_state(workflow, state_json, context.seed)
    if isinstance(saved_prompt, dict):
        for prompt_node in saved_prompt.values():
            if prompt_node.get("class_type") == "H3StudioDirector":
                inputs = prompt_node.setdefault("inputs", {})
                inputs["studio_state"] = state_json
                inputs["seed"] = int(context.seed)
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
        return super().save_images(images, filename_prefix, saved_prompt, saved_extra)


NODE_CLASS_MAPPINGS = {"H3StudioSaveImage": H3StudioSaveImage}
NODE_DISPLAY_NAME_MAPPINGS = {"H3StudioSaveImage": "H3 Studio · Save Restorable PNG"}
