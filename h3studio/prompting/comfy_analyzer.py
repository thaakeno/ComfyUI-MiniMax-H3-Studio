"""Cached native ComfyUI Qwen3-VL analysis and two-pass prompt direction."""

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
_WRITER_CACHE_KEY: tuple[Any, ...] | None = None
_WRITER_CACHE_VALUE: tuple[str, str] | None = None
_RETENTIONS = {"attribute_transfer", "fully_preserved", "partially_preserved", "reference_only"}

SYSTEM_INSTRUCTION = """You are the visual reference analyst for MiniMax H3 image generation.
Study every attached image pixel-by-pixel and use the user's exact request only to decide what each source contributes.
Return JSON only with this exact shape:
{"instruction":"one improved image-generation instruction using @Image1 tags","references":[{"ordinal":1,"role":"character","retention":"fully_preserved","description":"concise factual source-pixel observation"}]}

Allowed roles: auto, identity, face, character, style, composition, pose, outfit, object, environment, layout, typography, color_palette, lighting, texture, reference.
Allowed retention: attribute_transfer, fully_preserved, partially_preserved, reference_only.
Each description must contain only independently visible source facts in 8-24 words. Never copy a requested new action, prop, pose, gaze, clothing change, style, environment, or edit into a source description unless it is already visible in that image. Never write generic phrases such as 'visible information requested by the user'.
Rewrite the request into one precise 40-90 word instruction. Preserve every action, direction, expression, object, setting, assignment, exact text, and negative constraint. Use @Image1, @Image2 exactly; never use Picture, Subject, filenames, Markdown, headings, or newlines.
Translate every user-requested named style into concrete traits while retaining its canonical name. A JoJo request must say "JoJo's Bizarre Adventure-inspired anime" and include angular facial anatomy, bold black contours, cel shading, dense cross-hatched shadows, dramatic contrast, dynamic posing, and saturated colors. Explicitly replace the source photograph's rendering medium when another medium is requested.
Turn behavioral edits into visible constraints. Resolve pronouns. Use character or identity plus fully_preserved for identity; use object plus attribute_transfer for glasses and props. The requested changes override source pose, gaze, expression, clothing, or background.
Before answering, silently verify every @Image assignment and requested change. Do not emit prose outside JSON."""

WRITER_SYSTEM_INSTRUCTION = """You are the senior image prompt director for MiniMax H3.
You receive the user's exact request and factual source-image observations from a separate vision pass. You are not viewing pixels now. Expand them into one precise 200-450 word production instruction inside JSON: {"instruction":"..."}.

Preserve every requested action, direction, expression, object, environment, exact wording, negative constraint, and @Image assignment. Never replace @Image tags with Picture, Subject, filenames, Markdown, or internal identifiers. Resolve pronouns and make physical relationships explicit. References are source material, never extra panels, floating objects, duplicate bodies, mannequins, or a collage.

Treat interaction verbs as hard visible geometry. For "hold," describe which hand or both hands grip or support the object, visible finger contact, plausible weight, overlap, scale, and occlusion; the object may not merely float or sit independently in front of the subject. Apply the same concrete contact logic to wearing, carrying, eating, touching, and looking.

Describe the final composition, framing, viewpoint, body and gaze direction, expression, object interaction, lighting, palette, materials, depth, and rendering treatment where they help the request. Do not add unrelated story elements. Source observations are facts, not requested edits; never claim an absent edit was already visible.

For a named style, retain its canonical name and translate it into concrete traits. A JoJo request must explicitly say JoJo's Bizarre Adventure-inspired anime and include angular facial anatomy, bold black contours, cel shading, dense cross-hatched shadows, dramatic contrast, dynamic graphic posing, and saturated color design. State that this rendering replaces the source photographic medium while preserving assigned identity and objects.

Write connected production prose, not tag salad. Do not add audio, soundscape, music, motion, or video instructions. Output compact valid JSON only and silently check every @Image tag and requested constraint before answering."""


def _tensor_fingerprint(image: Any) -> str:
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
    labels = ("analyzer changed", "prompt changed", "analyzer detail changed", "reference images changed")
    for index, label in enumerate(labels):
        if previous[index] != current[index]:
            return label
    return "cache state changed"


def _json_object(text: str) -> dict[str, Any]:
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text or "").strip(), flags=re.IGNORECASE)
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Qwen3-VL returned no JSON object.")
    parsed = json.loads(value[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Qwen3-VL JSON was not an object.")
    return parsed


def _extract_analysis(text: str) -> dict[str, Any]:
    parsed = _json_object(text)
    if not isinstance(parsed.get("references"), list):
        raise ValueError("Qwen3-VL JSON did not contain a references list.")
    return parsed


def _extract_writer_instruction(text: str) -> str:
    instruction = " ".join(str(_json_object(text).get("instruction") or "").split())
    if not instruction:
        raise ValueError("Prompt writer JSON contained no instruction.")
    return instruction


def _writer_failures(candidate: str, original_prompt: str) -> list[str]:
    failures: list[str] = []
    count = len(candidate.split())
    if count < 180:
        failures.append(f"instruction has {count} words; minimum is 180")
    if count > 500:
        failures.append(f"instruction has {count} words; maximum is 500")
    if not set(mention_ordinals(original_prompt)).issubset(set(mention_ordinals(candidate))):
        failures.append("one or more @Image assignments were dropped")
    source, result = original_prompt.lower(), candidate.lower()
    constraints = {
        "right": ("right", "frame-right"),
        "left": ("left", "frame-left"),
        "smile": ("smile", "smiling"),
        "hold": ("hold", "holding", "grasp", "support"),
        "eat": ("eat", "eating", "bite", "biting"),
    }
    for trigger, alternatives in constraints.items():
        if trigger in source and not any(term in result for term in alternatives):
            failures.append(f"requested {trigger!r} constraint was omitted")
    if "hold" in source:
        contact_terms = ("hand", "finger", "grip", "contact", "support", "palm", "wrap")
        if not any(term in result for term in contact_terms):
            failures.append("holding instruction lacks visible hand-object contact geometry")
    if "jojo" in source:
        traits = (
            "jojo's bizarre adventure",
            "angular",
            "black contour",
            "cel shad",
            "cross-hatch",
            "contrast",
            "saturated",
        )
        missing = [trait for trait in traits if trait not in result]
        if missing:
            failures.append("JoJo style lacks concrete traits: " + ", ".join(missing))
    return failures


def _deterministic_writer_fallback(prompt: str, references: Sequence[ReferenceImage]) -> str:
    assignments = "; ".join(
        f"@Image{item.ordinal} supplies {item.effective_role} with {item.retention} retention"
        + (f", visibly described as {item.description.rstrip('.')}" if item.description else "")
        for item in references
    )
    style = ""
    if "jojo" in prompt.lower():
        style = (
            "Render the result as JoJo's Bizarre Adventure-inspired anime, replacing the source photographic medium "
            "with angular facial anatomy, bold black contours, crisp cel shading, dense cross-hatched shadows, "
            "dramatic contrast, dynamic graphic posing, and saturated color design."
        )
    sections = (
        f"Create one coherent finished still image that visibly fulfills this exact direction: {prompt}.",
        f"Reference contract: {assignments}.",
        "Preserve every named subject, assignment, action, direction, expression, prop, environment, and negative constraint. Resolve pronouns to the referenced subject and make gaze, head direction, body orientation, facial expression, and object interactions unambiguous in the final frame. For any request to hold or carry an object, show the named hand or both hands visibly gripping or supporting its weight, with fingers wrapped around it, correct contact, overlap, scale, and occlusion; never merely place the object independently in front of the subject.",
        "Use each source only for its assigned identity, object, wardrobe, style, pose, layout, lighting, or environmental function. References are source material, not additional subjects. Do not create a reference sheet, collage, split screen, floating accessory, duplicate body, mannequin, source panel, or unrequested source background. Do not let one source overwrite unrelated traits assigned to another.",
        "Compose a deliberate single frame with clear visual hierarchy, readable silhouette, coherent anatomy, credible perspective, intentional framing, and enough spatial separation for every requested detail to remain legible. Choose a camera distance and viewpoint that make the requested pose, gaze, expression, and transferred objects immediately visible. Establish a specific foreground, subject plane, and background relationship without distracting from the requested edit.",
        "Use motivated lighting with controlled highlights and shadows, consistent material response, purposeful depth, and a unified color relationship. Preserve recognizable identity through facial structure, proportions, silhouette, signature color placement, and source-specific design cues while changing only what the instruction requests. Make transferred accessories sit naturally on the target with correct scale, occlusion, contact, and perspective.",
        style,
        "Keep exact quoted wording unchanged. Do not add text, signatures, watermarks, unexplained people, unrelated props, sound, music, motion directions, or video language. Favor explicit visual evidence over vague quality adjectives. The output must be one internally consistent finished image whose requested edits are unmistakable at first glance and whose composition reads as an intentional final artwork rather than a demonstration of reference inputs.",
    )
    return " ".join(" ".join(sections).split())


def _run_prompt_writer(
    clip: Any,
    prompt: str,
    references: Sequence[ReferenceImage],
    *,
    writer_name: str,
    clip_loader: Any = None,
) -> tuple[str, str]:
    global _WRITER_CACHE_KEY, _WRITER_CACHE_VALUE
    facts = tuple((item.ordinal, item.effective_role, item.retention, item.description) for item in references)
    identity = writer_name or (type(clip).__name__ if clip is not None else "default")
    key = (str(identity), str(prompt), facts)
    with _CACHE_LOCK:
        if key == _WRITER_CACHE_KEY and _WRITER_CACHE_VALUE is not None:
            LOGGER.info("[H3 Studio - Prompt Director] Cache HIT | text generation skipped")
            return _WRITER_CACHE_VALUE[0], _WRITER_CACHE_VALUE[1] + " Cache: HIT."
    if clip is None and callable(clip_loader):
        LOGGER.info("[H3 Studio - Prompt Director] Loading writer: %s", writer_name or "selected model")
        clip = clip_loader()
    if clip is None:
        raise ValueError(
            "Two-pass prompt direction is enabled, but no full Qwen3-VL prompt writer is selected in H3 Studio Loader."
        )
    records = "\n".join(
        f"@Image{item.ordinal}: role={item.effective_role}; retention={item.retention}; source observation={item.description or 'no visual description available'}"
        for item in references
    )
    base = f"{WRITER_SYSTEM_INSTRUCTION}\n\nUSER REQUEST:\n{prompt}\n\nFACTUAL REFERENCE RECORDS:\n{records}"
    failures: list[str] = []
    started = time.perf_counter()
    for attempt in range(2):
        retry = "" if not failures else "\n\nVALIDATION FAILED. Rewrite completely and fix: " + "; ".join(failures)
        LOGGER.info("[H3 Studio - Prompt Director] Writing detailed brief | attempt %d/2 | text-only", attempt + 1)
        tokens = clip.tokenize(base + retry, images=[], thinking=False)
        generated = clip.generate(
            tokens,
            do_sample=True,
            max_length=900,
            temperature=0.65,
            top_k=20,
            top_p=0.88,
            min_p=0.02,
            repetition_penalty=1.08,
            seed=41 + attempt,
            presence_penalty=0.0,
        )
        decoded = clip.decode(generated, skip_special_tokens=True)
        if isinstance(decoded, (tuple, list)):
            decoded = decoded[0] if decoded else ""
        try:
            candidate = _extract_writer_instruction(str(decoded))
            failures = _writer_failures(candidate, prompt)
        except (ValueError, json.JSONDecodeError) as exc:
            candidate, failures = "", [str(exc)]
        if not failures:
            elapsed = time.perf_counter() - started
            note = f"Prompt director: {identity} produced and validated a {len(candidate.split())}-word text-only brief in {elapsed:.2f}s."
            with _CACHE_LOCK:
                _WRITER_CACHE_KEY, _WRITER_CACHE_VALUE = key, (candidate, note)
            LOGGER.info("[H3 Studio - Prompt Director] Complete | %d words | validated", len(candidate.split()))
            return candidate, note
        LOGGER.warning("[H3 Studio - Prompt Director] Validation failed | %s", "; ".join(failures))
    candidate = _deterministic_writer_fallback(prompt, references)
    note = "Prompt director: model output failed validation twice; used the complete deterministic fallback."
    with _CACHE_LOCK:
        _WRITER_CACHE_KEY, _WRITER_CACHE_VALUE = key, (candidate, note)
    LOGGER.warning("[H3 Studio - Prompt Director] Used deterministic fallback | %d words", len(candidate.split()))
    return candidate, note


def analyze_references(
    clip: Any,
    prompt: str,
    references: Sequence[ReferenceImage],
    images: Sequence[Any],
    *,
    analyzer_name: str = "",
    clip_loader: Any = None,
    max_image_edge: int = 512,
    deep_enhancement: bool = False,
    writer_clip: Any = None,
    writer_name: str = "",
    writer_loader: Any = None,
) -> tuple[tuple[ReferenceImage, ...], str, str]:
    """Inspect pixels once, then optionally run a cached text-only writing pass."""

    global _CACHE_KEY, _CACHE_VALUE
    max_image_edge = int(max_image_edge)
    if max_image_edge != 0:
        max_image_edge = max(256, min(1024, max_image_edge))
    if not images or not references:
        return tuple(references), str(prompt), "Image analysis: no references to inspect."
    identity = analyzer_name or (type(clip).__name__ if clip is not None else "default")
    key = (
        str(identity),
        str(prompt),
        int(max_image_edge),
        tuple(_image_key(reference, image) for reference, image in zip(references, images, strict=False)),
    )
    with _CACHE_LOCK:
        cache_hit = key == _CACHE_KEY and _CACHE_VALUE is not None
        cached = _CACHE_VALUE if cache_hit else None
        miss_reason = _cache_miss_reason(_CACHE_KEY, key)
    if cached is not None:
        analyzed = _apply_payload(references, cached[0])
        enhanced = _enhanced_instruction(cached[0], prompt)
        note = f"{cached[1]} Cache: HIT; vision generation skipped because prompt, images, and detail are unchanged."
        LOGGER.info("[H3 Studio - Vision] Cache HIT | reused %d source descriptions", len(analyzed))
    else:
        detail_label = "native original pixels" if max_image_edge == 0 else f"max edge {max_image_edge}px"
        started = time.perf_counter()
        LOGGER.info(
            "[H3 Studio - Vision] Cache MISS (%s) | %d reference(s) | %s", miss_reason, len(images), detail_label
        )
        if clip is None and callable(clip_loader):
            LOGGER.info("[H3 Studio - Vision] Loading analyzer: %s", identity)
            clip = clip_loader()
        if clip is None:
            raise ValueError(
                "Visual analysis requires a full Qwen3-VL checkpoint in ComfyUI/models/text_encoders. "
                "Select it in H3 Studio Loader; the H3 ConvRot encoder cannot generate descriptions."
            )
        numbered = "\n".join(
            f"Image {item.ordinal}: filename={item.filename}; current role={item.role}; current retention={item.retention}"
            for item in references
        )
        instruction = (
            f"{SYSTEM_INSTRUCTION}\n\nUSER REQUEST:\n{prompt}\n\nREFERENCE ORDER:\n{numbered}\n\n"
            f"Analyze exactly {len(images)} attached images and return exactly {len(images)} reference records."
        )
        analysis_images = [_prepare_image(image, max_image_edge) for image in images]
        LOGGER.info("[H3 Studio - Vision] Prepared %d analysis copies | H3 originals untouched", len(analysis_images))
        tokens = clip.tokenize(instruction, images=analysis_images, thinking=False)
        LOGGER.info("[H3 Studio - Vision] Inspecting pixels and writing factual source records...")
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
        payload = _extract_analysis(str(decoded))
        analyzed = _apply_payload(references, payload)
        enhanced = _enhanced_instruction(payload, prompt)
        note = (
            f"Image analysis: Qwen3-VL inspected {len(analyzed)} actual reference image(s) at {detail_label}; "
            "H3 originals were preserved."
        )
        with _CACHE_LOCK:
            _CACHE_KEY, _CACHE_VALUE = key, (payload, note)
        LOGGER.info(
            "[H3 Studio - Vision] Complete in %.2fs | %d factual source record(s)",
            time.perf_counter() - started,
            len(analyzed),
        )
    if deep_enhancement:
        enhanced, writer_note = _run_prompt_writer(
            writer_clip,
            prompt,
            analyzed,
            writer_name=writer_name,
            clip_loader=writer_loader,
        )
        note = f"{note} {writer_note}"
    return analyzed, enhanced, note


def _enhanced_instruction(payload: dict[str, Any], original_prompt: str) -> str:
    candidate = " ".join(str(payload.get("instruction") or "").split())
    if not candidate or len(candidate) > 1200:
        return str(original_prompt)
    if not set(mention_ordinals(original_prompt)).issubset(set(mention_ordinals(candidate))):
        LOGGER.warning("[H3 Studio - Vision] Rewrite dropped an @Image assignment; using the original prompt.")
        return str(original_prompt)
    return candidate


def _apply_payload(references: Sequence[ReferenceImage], payload: dict[str, Any]) -> tuple[ReferenceImage, ...]:
    by_ordinal = {
        int(item.get("ordinal", 0)): item
        for item in payload["references"]
        if isinstance(item, dict) and str(item.get("ordinal", "")).isdigit()
    }
    analyzed: list[ReferenceImage] = []
    for reference in references:
        item = by_ordinal.get(reference.ordinal, {})
        can_role = reference.role_auto or reference.role == "auto"
        can_retention = reference.retention_auto or reference.role == "auto"
        can_description = reference.description_auto or not reference.description.strip()
        role = str(item.get("role") or reference.role).strip().lower() if can_role else reference.role
        retention = (
            str(item.get("retention") or reference.retention).strip().lower() if can_retention else reference.retention
        )
        observed = " ".join(str(item.get("description") or "").split())
        description = observed if observed and can_description else reference.description
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
                role_auto=can_role,
                retention_auto=can_retention,
                description_auto=bool(observed and can_description),
                tags=tuple(dict.fromkeys((*reference.tags, "visually_analyzed"))),
            )
        )
    return tuple(analyzed)


def _prepare_image(image: Any, max_edge: int) -> Any:
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

        resized = functional.interpolate(
            image.permute(0, 3, 1, 2),
            size=(target_height, target_width),
            mode="bilinear",
            align_corners=False,
            antialias=True,
        )
        return resized.permute(0, 2, 3, 1)
    except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
        return image
