"""Native ComfyUI Qwen3-VL reference analysis.

The MiniMax H3 ConvRot encoder is intentionally truncated and has no language
model head, so it can condition H3 but cannot write captions.  This module uses
an optional full ComfyUI Qwen3-VL checkpoint to inspect the actual pixels, then
feeds concise observations back into the deterministic H3 prompt compiler.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from ..constants import REFERENCE_ROLES
from ..references import ReferenceImage, mention_ordinals

LOGGER = logging.getLogger(__name__)
_CACHE_LOCK = threading.RLock()
_CACHE_KEY: tuple[Any, ...] | None = None
_CACHE_VALUE: tuple[dict[str, Any], str] | None = None
_RETENTIONS = {"attribute_transfer", "fully_preserved", "partially_preserved", "reference_only"}

SYSTEM_INSTRUCTION = """You are the visual reference analyst for MiniMax H3 image generation.
Study every attached image pixel-by-pixel and use the user's exact request to decide what each image contributes.
Return JSON only, with this exact shape:
{"instruction":"one improved image-generation instruction using @Image1 tags","references":[{"ordinal":1,"role":"character","retention":"fully_preserved","description":"concise visible details relevant to the request"}]}

Allowed roles: auto, identity, face, character, style, composition, pose, outfit, object, environment, layout, typography, color_palette, lighting, texture, reference.
Allowed retention: attribute_transfer, fully_preserved, partially_preserved, reference_only.
Describe what is actually visible in 8-18 words: identity/appearance, object shape and color, clothing, pose, framing, style, lighting, or text as relevant. Never write generic phrases such as 'visible information requested by the user'. Keep the JSON compact and single-line.
Descriptions are observations of source pixels only. Never copy a requested new action, prop, pose, gaze, clothing change, environment, or edit into a source-image description unless that detail is independently visible in that source image. For example, if the user asks a person to hold a donut but the source person is not holding one, omit the donut from the source description; the prompt compiler will preserve the requested edit separately.
Rewrite the user's request into one clear 25-45 word instruction. Preserve every requested action, direction, expression, object, setting, and image assignment. Use @Image1, @Image2, etc. exactly; never use <Picture>, <Subject>, filenames, Markdown, headings, or newlines. Add only visually grounded specificity from the attached sources. Do not invent a new scene, camera, style, or action.
Use character/identity plus fully_preserved for the person whose identity must remain. Use object plus attribute_transfer for glasses, props, or isolated accessories. Preserve only role-relevant source details.
The user's requested changes are authoritative. Do not preserve a source pose, head direction, gaze, expression, clothing, or background when the user asks to change it. Interpret 'look to the right' as turn the head and direct the eyes toward frame-right unless the user explicitly defines another viewpoint.
Do not omit or weaken any user instruction. Do not emit Markdown or prose outside JSON."""


def _tensor_fingerprint(image: Any) -> str:
    """Hash pixels so recreated Comfy tensors remain the same image."""

    try:
        value = image.detach().to(device="cpu").contiguous()
        try:
            payload = value.numpy().tobytes()
        except (TypeError, RuntimeError):
            payload = value.float().numpy().tobytes()
        return hashlib.blake2b(payload, digest_size=16).hexdigest()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pointer = getattr(image, "data_ptr", None)
        identity = pointer() if callable(pointer) else id(image)
        return f"opaque:{type(image).__name__}:{identity}"


def _image_key(reference: ReferenceImage, image: Any) -> tuple[Any, ...]:
    shape = tuple(getattr(image, "shape", ()))
    if reference.fingerprint:
        return "declared", reference.fingerprint, shape
    if reference.storage_name:
        return "storage", reference.storage_name, _tensor_fingerprint(image), shape
    return "pixels", reference.filename, _tensor_fingerprint(image), shape


def _cache_miss_reason(previous: tuple[Any, ...] | None, current: tuple[Any, ...]) -> str:
    if previous is None:
        return "cold cache"
    if previous[0] != current[0]:
        return "analyzer changed"
    if previous[1] != current[1]:
        return "prompt changed"
    if previous[2] != current[2]:
        return "analyzer detail changed"
    if previous[3] != current[3]:
        return "reference images changed"
    return "cache state changed"


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
    *,
    analyzer_name: str = "",
    clip_loader: Any = None,
    max_image_edge: int = 512,
) -> tuple[tuple[ReferenceImage, ...], str, str]:
    """Inspect all reference tensors in one cached Qwen3-VL generation."""

    global _CACHE_KEY, _CACHE_VALUE
    max_image_edge = int(max_image_edge)
    if max_image_edge != 0:
        max_image_edge = max(256, min(1024, max_image_edge))
    if not images or not references:
        return tuple(references), str(prompt), "Image analysis: no references to inspect."
    key = (
        str(analyzer_name or (type(clip).__name__ if clip is not None else "default")),
        str(prompt),
        int(max_image_edge),
        tuple(_image_key(reference, image) for reference, image in zip(references, images, strict=False)),
    )
    with _CACHE_LOCK:
        if key == _CACHE_KEY and _CACHE_VALUE is not None:
            analyzed = _apply_payload(references, _CACHE_VALUE[0])
            note = f"{_CACHE_VALUE[1]} Cache: HIT; Qwen generation skipped because prompt and images are unchanged."
            LOGGER.info("[H3 Studio · Vision] Cache HIT | reused %d reference analyses | Qwen skipped", len(analyzed))
            return analyzed, _enhanced_instruction(_CACHE_VALUE[0], prompt), note
        miss_reason = _cache_miss_reason(_CACHE_KEY, key)
    detail_label = "Native · original pixels" if max_image_edge == 0 else f"max edge {max_image_edge}px"
    started = time.perf_counter()
    LOGGER.info(
        "[H3 Studio · Vision] Cache MISS (%s) | %d reference(s) | %s",
        miss_reason,
        len(images),
        detail_label,
    )
    if clip is None and callable(clip_loader):
        LOGGER.info("[H3 Studio · Vision] Loading Qwen3-VL analyzer: %s", analyzer_name or "selected model")
        clip = clip_loader()
    if clip is None:
        raise ValueError(
            "Visual reference analysis requires a full Qwen3-VL analyzer. Download "
            "qwen3vl_4b_fp8_scaled.safetensors into ComfyUI/models/text_encoders, select it in H3 Studio Loader, "
            "and connect the Loader bundle to the Director. The H3 ConvRot encoder cannot generate descriptions."
        )

    numbered = "\n".join(
        f"Image {reference.ordinal}: filename={reference.filename}; current role={reference.role}; current retention={reference.retention}"
        for reference in references
    )
    instruction = (
        f"{SYSTEM_INSTRUCTION}\n\nUSER REQUEST:\n{prompt}\n\nREFERENCE ORDER:\n{numbered}\n\n"
        f"Analyze exactly {len(images)} attached images and return exactly {len(images)} reference records."
    )
    analysis_images = [_prepare_image(image, max_image_edge) for image in images]
    LOGGER.info(
        "[H3 Studio · Vision] Prepared %d analysis image(s) | %s | H3 inputs remain untouched",
        len(analysis_images),
        detail_label,
    )
    tokens = clip.tokenize(instruction, images=analysis_images, thinking=False)
    LOGGER.info("[H3 Studio · Vision] Reading pixels and writing the enhanced instruction…")
    generated = clip.generate(
        tokens,
        do_sample=False,
        max_length=min(768, 96 + len(images) * 72),
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
    analyzed = _apply_payload(references, payload)
    enhanced = _enhanced_instruction(payload, prompt)
    note = (
        f"Image analysis: Qwen3-VL inspected and enhanced the instruction from {len(analyzed)} actual "
        f"reference image(s) at {detail_label}; H3 originals were preserved."
    )
    with _CACHE_LOCK:
        _CACHE_KEY = key
        _CACHE_VALUE = payload, note
    LOGGER.info(
        "[H3 Studio · Vision] Complete in %.2fs | %d reference(s) described | instruction enhanced",
        time.perf_counter() - started,
        len(analyzed),
    )
    return analyzed, enhanced, note


def _enhanced_instruction(payload: dict[str, Any], original_prompt: str) -> str:
    """Accept Qwen's rewrite only when every referenced image remains assigned."""

    candidate = " ".join(str(payload.get("instruction") or "").split())
    if not candidate or len(candidate) > 1200:
        return str(original_prompt)
    required = set(mention_ordinals(original_prompt))
    present = set(mention_ordinals(candidate))
    if not required.issubset(present):
        LOGGER.warning("[H3 Studio · Vision] Rewrite dropped an @Image assignment; using the original prompt.")
        return str(original_prompt)
    return candidate


def _apply_payload(
    references: Sequence[ReferenceImage],
    payload: dict[str, Any],
) -> tuple[ReferenceImage, ...]:
    """Apply cached observations without overwriting current manual card edits."""

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

    return tuple(analyzed)


def _prepare_image(image: Any, max_edge: int) -> Any:
    """Downscale only the analyzer copy; H3 still receives the original tensor."""

    try:
        if max_edge == 0:
            return image
        _, height, width, _ = image.shape
        longest = max(int(height), int(width))
        if longest <= max_edge:
            return image
        scale = max_edge / longest
        target_height = max(32, round((int(height) * scale) / 32) * 32)
        target_width = max(32, round((int(width) * scale) / 32) * 32)
        import torch.nn.functional as functional

        channels_first = image.permute(0, 3, 1, 2)
        resized = functional.interpolate(
            channels_first,
            size=(target_height, target_width),
            mode="bilinear",
            align_corners=False,
            antialias=True,
        )
        return resized.permute(0, 2, 3, 1)
    except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
        return image
