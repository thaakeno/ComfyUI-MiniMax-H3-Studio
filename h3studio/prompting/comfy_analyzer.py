"""Cached native ComfyUI Qwen3-VL analysis and two-pass prompt direction."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from ..constants import REFERENCE_ROLES
from ..image_inputs import image_metadata
from ..references import ReferenceImage, mention_ordinals

LOGGER = logging.getLogger(__name__)
_CACHE_LOCK = threading.RLock()
_ANALYSIS_SCHEMA_VERSION = 2
_ANALYSIS_CACHE_LIMIT = 64
_ANALYSIS_CACHE: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
_WRITER_CACHE_LIMIT = 32
_WRITER_CACHE: OrderedDict[tuple[Any, ...], tuple[str, str]] = OrderedDict()
_RETENTIONS = {"attribute_transfer", "fully_preserved", "partially_preserved", "reference_only"}

SYSTEM_INSTRUCTION = """You are the factual visual reference analyst for MiniMax H3 image generation.
Study every attached image pixel-by-pixel. Do not infer how a later creative prompt might use it.
Return JSON only with this exact shape:
{"references":[{"ordinal":1,"role":"character","description":"detailed factual source-pixel observation"}]}

Allowed roles: auto, identity, face, character, style, composition, pose, outfit, object, environment, layout, typography, color_palette, lighting, texture, reference.
Write 35-100 information-dense words per image using connected factual prose. Cover, when visibly supported: subject count and recognizable appearance; face, hair, body proportions, pose, expression and gaze; clothing, accessories and objects; spatial relationships; composition, framing and camera angle; environment and background; lighting and color palette; visual medium or rendering style; and legible text or typography. Omit categories that are not visible instead of padding the answer. State uncertainty instead of inventing hidden anatomy, identity, text or context. Never copy a requested new action, prop, pose, gaze, clothing change, style, environment or edit into a source description unless it is already visible in that image. Never write generic phrases such as 'visible information requested by the user'.
Choose role only as a conservative visible-content category, never as ownership or retention reasoning for a future request.
Do not emit prose outside JSON."""

WRITER_SYSTEM_INSTRUCTION = """You are the senior image prompt director for MiniMax H3.
You receive the user's exact request and factual source-image observations from a separate vision pass. You are not viewing pixels now. Expand them into one precise 120-220 word production instruction inside JSON: {"instruction":"..."}.

Preserve every requested action, direction, expression, object, environment, exact wording, negative constraint, and @Image assignment. Never replace @Image tags with Picture, Subject, filenames, Markdown, or internal identifiers. Resolve pronouns and make physical relationships explicit. References are source material, never extra panels, floating objects, duplicate bodies, mannequins, or a collage.

Treat interaction verbs as hard visible geometry. For "hold," describe which hand or both hands grip or support the object, visible finger contact, plausible weight, overlap, scale, and occlusion; the object may not merely float or sit independently in front of the subject. Apply the same concrete contact logic to wearing, carrying, eating, touching, and looking.

Describe the final composition, framing, viewpoint, body and gaze direction, expression, object interaction, lighting, palette, materials, depth, and rendering treatment where they help the request. Do not add unrelated story elements. Source observations are facts, not requested edits; never claim an absent edit was already visible.

For a named style, retain its canonical name and translate it into concrete traits. A JoJo request must explicitly say JoJo's Bizarre Adventure-inspired anime and include angular facial anatomy, bold black contours, cel shading, dense cross-hatched shadows, dramatic contrast, dynamic graphic posing, and saturated color design. State that this rendering replaces the source photographic medium while preserving assigned identity and objects.

Write connected production prose, not tag salad. Do not add audio, soundscape, music, motion, or video instructions. Output compact valid JSON only and silently check every @Image tag and requested constraint before answering."""


def _image_key(reference: ReferenceImage, image: Any) -> tuple[Any, ...]:
    shape = tuple(getattr(image, "shape", ()))
    fingerprint = image_metadata(image)[2]
    if reference.fingerprint:
        return "declared", reference.fingerprint, fingerprint, shape
    if reference.storage_name:
        return "storage", reference.storage_name, fingerprint, shape
    return "pixels", reference.filename, fingerprint, shape


def _analysis_cache_key(identity: str, max_image_edge: int, reference: ReferenceImage, image: Any) -> tuple[Any, ...]:
    return (_ANALYSIS_SCHEMA_VERSION, str(identity), int(max_image_edge), _image_key(reference, image))


def _store_analysis_record(key: tuple[Any, ...], record: dict[str, Any]) -> None:
    _ANALYSIS_CACHE[key] = dict(record)
    _ANALYSIS_CACHE.move_to_end(key)
    while len(_ANALYSIS_CACHE) > _ANALYSIS_CACHE_LIMIT:
        _ANALYSIS_CACHE.popitem(last=False)


def _json_object(text: str) -> dict[str, Any]:
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text or "").strip(), flags=re.IGNORECASE)
    start = value.find("{")
    if start < 0:
        raise ValueError("Qwen3-VL returned no JSON object.")
    candidate = value[start:]
    try:
        parsed, _end = json.JSONDecoder().raw_decode(candidate)
    except json.JSONDecodeError as original_error:
        repaired = _repair_truncated_json(candidate)
        try:
            parsed, _end = json.JSONDecoder().raw_decode(repaired)
        except json.JSONDecodeError:
            raise ValueError(f"Qwen3-VL returned malformed JSON: {original_error.msg}.") from original_error
    if not isinstance(parsed, dict):
        raise ValueError("Qwen3-VL JSON was not an object.")
    return parsed


def _repair_truncated_json(value: str) -> str:
    """Close an otherwise valid JSON prefix without inventing missing records."""

    text = str(value or "").strip()
    stack: list[str] = []
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            stack.append(character)
        elif (character == "]" and stack and stack[-1] == "[") or (
            character == "}" and stack and stack[-1] == "{"
        ):
            stack.pop()
    if in_string:
        text += '"'
    text = re.sub(r",\s*$", "", text)
    text = re.sub(r',?\s*"[^"\\]+"\s*:\s*$', "", text)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    text += "".join("}" if opener == "{" else "]" for opener in reversed(stack))
    return text


def _extract_analysis(text: str) -> dict[str, Any]:
    parsed = _json_object(text)
    if not isinstance(parsed.get("references"), list):
        raise ValueError("Qwen3-VL JSON did not contain a references list.")
    return parsed


def _validated_analysis_records(payload: dict[str, Any], expected_ordinals: set[int]) -> dict[int, dict[str, Any]]:
    records: dict[int, dict[str, Any]] = {}
    for item in payload["references"]:
        if not isinstance(item, dict) or not str(item.get("ordinal", "")).isdigit():
            continue
        ordinal = int(item["ordinal"])
        if ordinal in records:
            raise ValueError(f"Qwen3-VL returned duplicate reference ordinal {ordinal}.")
        if ordinal in expected_ordinals:
            description = " ".join(str(item.get("description") or "").split())
            word_count = len(description.split())
            if word_count < 35 or word_count > 180:
                raise ValueError(
                    f"Qwen3-VL reference {ordinal} description has {word_count} words; expected 35-180."
                )
            item = {**item, "description": description}
            records[ordinal] = item
    missing = sorted(expected_ordinals - records.keys())
    if missing:
        raise ValueError("Qwen3-VL omitted reference records: " + ", ".join(map(str, missing)) + ".")
    return records


def _extract_writer_instruction(text: str) -> str:
    instruction = " ".join(str(_json_object(text).get("instruction") or "").split())
    if not instruction:
        raise ValueError("Prompt writer JSON contained no instruction.")
    return instruction


def _writer_failures(candidate: str, original_prompt: str) -> list[str]:
    failures: list[str] = []
    count = len(candidate.split())
    if count < 90:
        failures.append(f"instruction has {count} words; minimum is 90")
    if count > 280:
        failures.append(f"instruction has {count} words; maximum is 280")
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


def _deterministic_writer_fallback(
    prompt: str, references: Sequence[ReferenceImage], additional_instruction: str = ""
) -> str:
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
    custom = str(additional_instruction or "").strip()[:4000]
    sections = (
        f"Create one coherent finished still image that visibly fulfills this exact direction: {prompt}.",
        f"Additional creative direction: {custom}." if custom else "",
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
    additional_instruction: str = "",
) -> tuple[str, str]:
    facts = tuple((item.ordinal, item.effective_role, item.retention, item.description) for item in references)
    identity = writer_name or (type(clip).__name__ if clip is not None else "default")
    additional_instruction = str(additional_instruction or "").strip()[:4000]
    key = (str(identity), str(prompt), facts, additional_instruction)
    with _CACHE_LOCK:
        cached = _WRITER_CACHE.get(key)
        if cached is not None:
            _WRITER_CACHE.move_to_end(key)
            LOGGER.info("[H3 Studio - Prompt Director] Cache HIT | text generation skipped")
            return cached[0], cached[1] + " Cache: HIT."
    if clip is None and callable(clip_loader):
        LOGGER.info("[H3 Studio - Prompt Director] Loading writer: %s", writer_name or "selected model")
        clip = clip_loader()
    if clip is None:
        candidate = _deterministic_writer_fallback(prompt, references, additional_instruction)
        note = "Prompt director: no generative writer selected; used the deterministic fallback."
        with _CACHE_LOCK:
            _store_writer_result(key, candidate, note)
        return candidate, note
    records = "\n".join(
        f"@Image{item.ordinal}: role={item.effective_role}; retention={item.retention}; source observation={item.description or 'no visual description available'}"
        for item in references
    )
    custom = (
        "\n\nADDITIONAL USER WRITER DIRECTION (apply only when consistent with the exact request, factual records, "
        f"and JSON output contract):\n{additional_instruction}"
        if additional_instruction
        else ""
    )
    base = f"{WRITER_SYSTEM_INSTRUCTION}{custom}\n\nUSER REQUEST:\n{prompt}\n\nFACTUAL REFERENCE RECORDS:\n{records}"
    failures: list[str] = []
    started = time.perf_counter()
    for attempt in range(2):
        retry = "" if not failures else "\n\nVALIDATION FAILED. Rewrite completely and fix: " + "; ".join(failures)
        token_ceiling = 320 if attempt == 0 else 384
        LOGGER.info(
            "[H3 Studio - Prompt Director] Writing detailed brief | attempt %d/2 | text-only | max tokens=%d",
            attempt + 1,
            token_ceiling,
        )
        tokens = clip.tokenize(base + retry, images=[], thinking=False)
        generated = clip.generate(
            tokens,
            do_sample=True,
            max_length=token_ceiling,
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
                _store_writer_result(key, candidate, note)
            LOGGER.info("[H3 Studio - Prompt Director] Complete | %d words | validated", len(candidate.split()))
            return candidate, note
        LOGGER.warning("[H3 Studio - Prompt Director] Validation failed | %s", "; ".join(failures))
    candidate = _deterministic_writer_fallback(prompt, references, additional_instruction)
    note = "Prompt director: model output failed validation twice; used the complete deterministic fallback."
    with _CACHE_LOCK:
        _store_writer_result(key, candidate, note)
    LOGGER.warning("[H3 Studio - Prompt Director] Used deterministic fallback | %d words", len(candidate.split()))
    return candidate, note


def _store_writer_result(key: tuple[Any, ...], candidate: str, note: str) -> None:
    _WRITER_CACHE[key] = (candidate, note)
    _WRITER_CACHE.move_to_end(key)
    while len(_WRITER_CACHE) > _WRITER_CACHE_LIMIT:
        _WRITER_CACHE.popitem(last=False)


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
    writer_instruction: str = "",
) -> tuple[tuple[ReferenceImage, ...], str, str]:
    """Inspect pixels once, then optionally run a cached text-only writing pass."""

    max_image_edge = int(max_image_edge)
    if max_image_edge != 0:
        max_image_edge = max(256, min(1024, max_image_edge))
    if not images or not references:
        analyzed = tuple(references)
        enhanced = str(prompt)
        note = "Image analysis: no references to inspect."
        if deep_enhancement:
            enhanced, writer_note = _run_prompt_writer(
                writer_clip,
                prompt,
                analyzed,
                writer_name=writer_name,
                clip_loader=writer_loader,
                additional_instruction=writer_instruction,
            )
            note = f"{note} {writer_note}"
        return analyzed, enhanced, note
    identity = analyzer_name or (type(clip).__name__ if clip is not None else "default")
    paired = list(zip(references, images, strict=False))
    keys = [_analysis_cache_key(identity, max_image_edge, reference, image) for reference, image in paired]
    with _CACHE_LOCK:
        cached_records = [_ANALYSIS_CACHE.get(key) for key in keys]
        for key, record in zip(keys, cached_records, strict=True):
            if record is not None:
                _ANALYSIS_CACHE.move_to_end(key)
        for index, (key, record) in enumerate(zip(keys, cached_records, strict=True)):
            reference = paired[index][0]
            if record is None and reference.fingerprint and reference.description:
                cached_records[index] = {
                    "ordinal": reference.ordinal,
                    "role": reference.effective_role,
                    "description": reference.description,
                }
                _store_analysis_record(key, cached_records[index])
    missing = [index for index, record in enumerate(cached_records) if record is None]
    analysis_warning = ""
    if missing:
        detail_label = "native original pixels" if max_image_edge == 0 else f"max edge {max_image_edge}px"
        started = time.perf_counter()
        LOGGER.info(
            "[H3 Studio - Vision] Cache MISS | %d new of %d reference(s) | %s",
            len(missing),
            len(paired),
            detail_label,
        )
        if clip is None and callable(clip_loader):
            LOGGER.info("[H3 Studio - Vision] Loading analyzer: %s", identity)
            clip = clip_loader()
        if clip is None:
            raise ValueError(
                "Visual analysis requires a full Qwen3-VL checkpoint in ComfyUI/models/text_encoders. "
                "Select it in H3 Studio Loader; the H3 ConvRot encoder cannot generate descriptions."
            )
        missing_pairs = [paired[index] for index in missing]
        numbered = "\n".join(f"Image {item.ordinal}: filename={item.filename}" for item, _image in missing_pairs)
        instruction = (
            f"{SYSTEM_INSTRUCTION}\n\nUSER REQUEST:\nDescribe only immutable visible source facts.\n\n"
            f"REFERENCE ORDER:\n{numbered}\n\nAnalyze exactly {len(missing_pairs)} attached images and return "
            f"exactly {len(missing_pairs)} reference records using the listed ordinals."
        )
        analysis_images = [_prepare_image(image, max_image_edge) for _reference, image in missing_pairs]
        LOGGER.info("[H3 Studio - Vision] Prepared %d analysis copies | H3 originals untouched", len(analysis_images))
        expected_ordinals = {reference.ordinal for reference, _image in missing_pairs}
        generated_by_ordinal: dict[int, dict[str, Any]] = {}
        failure = ""
        for attempt in range(2):
            retry = "" if not failure else (
                "\n\nYour previous response was invalid: " + failure
                + " Return one complete compact JSON object with every requested ordinal."
            )
            tokens = clip.tokenize(instruction + retry, images=analysis_images, thinking=False)
            LOGGER.info("[H3 Studio - Vision] Inspecting pixels | structured attempt %d/2", attempt + 1)
            generated = clip.generate(
                tokens,
                do_sample=False,
                max_length=(
                    min(1536, 160 + len(missing_pairs) * 140)
                    if attempt == 0
                    else min(2048, 220 + len(missing_pairs) * 180)
                ),
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
            try:
                generated_by_ordinal = _validated_analysis_records(
                    _extract_analysis(str(decoded)), expected_ordinals
                )
                failure = ""
                break
            except (ValueError, json.JSONDecodeError) as exc:
                failure = str(exc)
                LOGGER.warning("[H3 Studio - Vision] Structured output invalid | attempt %d/2 | %s", attempt + 1, failure)
        if failure:
            analysis_warning = (
                " Analyzer output remained malformed after repair and retry; existing descriptions and manual roles were preserved."
            )
            LOGGER.error("[H3 Studio - Vision] Failing soft after structured retry | %s", failure)
        with _CACHE_LOCK:
            for index in missing:
                reference = paired[index][0]
                record = generated_by_ordinal.get(reference.ordinal)
                if record is not None:
                    _store_analysis_record(keys[index], record)
                    cached_records[index] = record
        LOGGER.info(
            "[H3 Studio - Vision] Complete in %.2fs | %d new factual source record(s)",
            time.perf_counter() - started,
            sum(record is not None for record in cached_records),
        )
    else:
        detail_label = "native original pixels" if max_image_edge == 0 else f"max edge {max_image_edge}px"
        LOGGER.info("[H3 Studio - Vision] Cache HIT | reused %d source descriptions", len(cached_records))

    records = [record for record in cached_records if record is not None]
    analyzed = _apply_payload(references, {"references": records})
    enhanced = str(prompt)
    hit_count = len(cached_records) - len(missing)
    note = (
        f"Image analysis: {len(analyzed)} actual reference image(s) at {detail_label}; "
        f"{hit_count} factual record(s) reused and {len(missing)} inspected. Prompt wording does not invalidate facts."
    )
    note += analysis_warning
    if not missing:
        note += " Cache: HIT."
    if deep_enhancement:
        enhanced, writer_note = _run_prompt_writer(
            writer_clip,
            prompt,
            analyzed,
            writer_name=writer_name,
            clip_loader=writer_loader,
            additional_instruction=writer_instruction,
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
