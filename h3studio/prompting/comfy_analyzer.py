"""Native ComfyUI Qwen3-VL reference analysis.

The MiniMax H3 ConvRot encoder is intentionally truncated and has no language
model head, so it can condition H3 but cannot write captions.  This module uses
an optional full ComfyUI Qwen3-VL checkpoint to inspect the actual pixels, then
feeds concise observations back into the deterministic H3 prompt compiler.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from ..constants import REFERENCE_ROLES
from ..references import ReferenceImage

LOGGER = logging.getLogger(__name__)
_CACHE_LOCK = threading.RLock()
_CACHE_KEY: tuple[Any, ...] | None = None
_CACHE_VALUE: tuple[tuple[ReferenceImage, ...], str] | None = None
_RETENTIONS = {"attribute_transfer", "fully_preserved", "partially_preserved", "reference_only"}

SYSTEM_INSTRUCTION = """You are the visual reference analyst for MiniMax H3 image generation.
Study every attached image pixel-by-pixel and use the user's exact request to decide what each image contributes.
Return JSON only, with this exact shape:
{"references":[{"ordinal":1,"role":"character","retention":"fully_preserved","description":"concise visible details relevant to the request"}]}

Allowed roles: auto, identity, face, character, style, composition, pose, outfit, object, environment, layout, typography, color_palette, lighting, texture, reference.
Allowed retention: attribute_transfer, fully_preserved, partially_preserved, reference_only.
Describe what is actually visible: identity/appearance, object shape and color, clothing, pose, framing, style, lighting, or text as relevant. Never write generic phrases such as 'visible information requested by the user'.
Use character/identity plus fully_preserved for the person whose identity must remain. Use object plus attribute_transfer for glasses, props, or isolated accessories. Preserve only role-relevant source details.
The user's requested changes are authoritative. Do not preserve a source pose, head direction, gaze, expression, clothing, or background when the user asks to change it. Interpret 'look to the right' as turn the head and direct the eyes toward frame-right unless the user explicitly defines another viewpoint.
Do not rewrite, summarize, improve, or omit any user instruction. Do not emit Markdown or prose outside JSON."""


def _image_key(image: Any) -> tuple[Any, ...]:
    pointer = getattr(image, "data_ptr", None)
    identity = pointer() if callable(pointer) else id(image)
    # torch.inference_mode() tensors deliberately have no readable version
    # counter and raise RuntimeError when `_version` is accessed.
    try:
        version = image._version
    except (AttributeError, RuntimeError):
        version = None
    return identity, version, tuple(getattr(image, "shape", ()))


def _extract_json(text: str) -> dict[str, Any]:
    value = str(text or "").strip()
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE)
    start = value.find("{")
    end = value.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Qwen3-VL returned no JSON object.")
    parsed = json.loads(value[start : end + 1])
    if not isinstance(parsed, dict) or not isinstance(parsed.get("references"), list):
        raise ValueError("Qwen3-VL JSON did not contain a references list.")
    return parsed


def analyze_references(
    clip: Any,
    prompt: str,
    references: Sequence[ReferenceImage],
    images: Sequence[Any],
) -> tuple[tuple[ReferenceImage, ...], str]:
    """Inspect all reference tensors in one cached Qwen3-VL generation."""

    global _CACHE_KEY, _CACHE_VALUE
    if not images or not references:
        return tuple(references), "Image analysis: no references to inspect."
    if clip is None:
        raise ValueError(
            "Visual reference analysis requires a full Qwen3-VL analyzer. Download "
            "qwen3vl_4b_fp8_scaled.safetensors into ComfyUI/models/text_encoders, select it in H3 Studio Loader, "
            "and connect the Loader bundle to the Director. The H3 ConvRot encoder cannot generate descriptions."
        )

    reference_key = tuple(
        (
            reference.ordinal,
            "<auto>" if reference.role_auto or reference.role == "auto" else reference.role,
            "<auto>" if reference.retention_auto or reference.role == "auto" else reference.retention,
            "<auto>" if reference.description_auto or not reference.description.strip() else reference.description,
        )
        for reference in references
    )
    key = (id(clip), str(prompt), reference_key, tuple(_image_key(image) for image in images))
    with _CACHE_LOCK:
        if key == _CACHE_KEY and _CACHE_VALUE is not None:
            return _CACHE_VALUE[0], f"{_CACHE_VALUE[1]} Cache: HIT."

    numbered = "\n".join(
        f"Image {reference.ordinal}: filename={reference.filename}; current role={reference.role}; current retention={reference.retention}"
        for reference in references
    )
    instruction = (
        f"{SYSTEM_INSTRUCTION}\n\nUSER REQUEST:\n{prompt}\n\nREFERENCE ORDER:\n{numbered}\n\n"
        f"Analyze exactly {len(images)} attached images and return exactly {len(images)} reference records."
    )
    tokens = clip.tokenize(instruction, images=list(images), thinking=False)
    generated = clip.generate(
        tokens,
        do_sample=False,
        max_length=1100,
        temperature=1.0,
        top_k=0,
        top_p=1.0,
        min_p=0.0,
        repetition_penalty=1.05,
        seed=0,
        presence_penalty=0.0,
    )
    decoded = clip.decode(generated, skip_special_tokens=True)
    if isinstance(decoded, (tuple, list)):
        decoded = decoded[0] if decoded else ""
    payload = _extract_json(str(decoded))
    by_ordinal = {
        int(item.get("ordinal", 0)): item
        for item in payload["references"]
        if isinstance(item, dict) and str(item.get("ordinal", "")).isdigit()
    }

    analyzed: list[ReferenceImage] = []
    for reference in references:
        item = by_ordinal.get(reference.ordinal, {})
        can_update_role = reference.role_auto or reference.role == "auto"
        can_update_retention = reference.retention_auto or reference.role == "auto"
        can_update_description = reference.description_auto or not reference.description.strip()
        role = str(item.get("role") or reference.role).strip().lower() if can_update_role else reference.role
        retention = (
            str(item.get("retention") or reference.retention).strip().lower()
            if can_update_retention
            else reference.retention
        )
        analyzed_description = " ".join(str(item.get("description") or "").split())
        description = (
            analyzed_description
            if analyzed_description and can_update_description
            else reference.description
        )
        if role not in REFERENCE_ROLES:
            role = reference.role
        if retention not in _RETENTIONS:
            retention = reference.retention
        analyzed.append(
            replace(
                reference,
                role=role,
                retention=retention,
                description=description,
                role_auto=can_update_role,
                retention_auto=can_update_retention,
                description_auto=bool(analyzed_description and can_update_description),
                tags=tuple(dict.fromkeys((*reference.tags, "visually_analyzed"))),
            )
        )

    note = f"Image analysis: Qwen3-VL inspected {len(analyzed)} actual reference image(s)."
    result = tuple(analyzed), note
    with _CACHE_LOCK:
        _CACHE_KEY = key
        _CACHE_VALUE = result
    LOGGER.info("[H3 Studio] %s", note)
    return result
