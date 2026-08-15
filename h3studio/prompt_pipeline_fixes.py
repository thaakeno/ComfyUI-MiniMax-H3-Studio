"""Fast, validated Director prompt-prep path.

When visual analysis and prompt direction use the same Qwen checkpoint and every
connected reference is a fresh cache miss, one multimodal generation can return
both factual source records and the final H3 instruction.  The old two-pass path
remains the fallback for mixed caches, mixed models, or invalid structured output.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

LOGGER = logging.getLogger(__name__)

FUSED_SYSTEM_INSTRUCTION = """You are MiniMax H3 Studio's visual analyst and image prompt director.
Inspect every attached image carefully, then return ONE compact JSON object with this exact shape:
{"references":[{"ordinal":1,"role":"character","description":"35-100 words of factual visible source details"}],"instruction":"120-220 word final image production instruction"}

REFERENCE RECORD RULES:
The references array is factual source-pixel analysis only. Never copy requested edits into a source description unless they are already visible. State only visible subject appearance, face/hair, body proportions when visible, pose, expression, gaze, clothing, accessories, objects, composition, camera angle, environment, lighting, palette, medium/style, and legible text. Omit unsupported details. Choose a conservative visible-content role. Do not infer ownership from the later creative request.

FINAL INSTRUCTION RULES:
The instruction must preserve the user's exact request, every @Image assignment, requested action, direction, gaze, expression, object, environment, quoted text and negative constraint. References are source material, never extra panels, floating objects, duplicate bodies, mannequins, or a collage. Resolve pronouns and physical relationships explicitly. For hold/carry/wear/touch/eat interactions, describe visible contact, plausible grip/support, overlap, scale and occlusion. Preserve assigned identity and source attributes while changing only what the request asks. Use connected production prose, not tag salad. Do not add audio, music, motion or video language. Keep generic styles generic; retain a named style only when the user named it.

Output JSON only."""


def _same_model(analyzer_name: str, writer_name: str) -> bool:
    left = "".join(ch for ch in str(analyzer_name or "").lower() if ch.isalnum())
    right = "".join(ch for ch in str(writer_name or "").lower() if ch.isalnum())
    return bool(left and right and left == right)


def _decoded_text(clip: Any, generated: Any) -> str:
    decoded = clip.decode(generated, skip_special_tokens=True)
    if isinstance(decoded, (tuple, list)):
        decoded = decoded[0] if decoded else ""
    return str(decoded or "")


def install() -> None:
    from .prompting import comfy_analyzer as analyzer

    original = analyzer.analyze_references
    if bool(getattr(original, "__h3studio_fused_prompt_v2__", False)):
        return

    def analyze_references(
        clip: Any,
        prompt: str,
        references,
        images,
        *,
        analyzer_name: str = "",
        clip_loader: Any = None,
        max_image_edge: int = 512,
        deep_enhancement: bool = False,
        writer_clip: Any = None,
        writer_name: str = "",
        writer_loader: Any = None,
        writer_instruction: str = "",
    ):
        # Keep all ordinary paths exactly as before. The fused path is deliberately
        # narrow: same model, fresh complete image set, deep enhancement enabled.
        if (
            not deep_enhancement
            or not references
            or not images
            or len(references) != len(images)
            or not _same_model(analyzer_name, writer_name)
        ):
            return original(
                clip,
                prompt,
                references,
                images,
                analyzer_name=analyzer_name,
                clip_loader=clip_loader,
                max_image_edge=max_image_edge,
                deep_enhancement=deep_enhancement,
                writer_clip=writer_clip,
                writer_name=writer_name,
                writer_loader=writer_loader,
                writer_instruction=writer_instruction,
            )

        edge = int(max_image_edge)
        if edge != 0:
            edge = max(256, min(1024, edge))
        identity = analyzer_name or (type(clip).__name__ if clip is not None else "default")
        paired = list(zip(references, images, strict=True))
        keys = [analyzer._analysis_cache_key(identity, edge, reference, image) for reference, image in paired]
        with analyzer._CACHE_LOCK:
            cached = [analyzer._ANALYSIS_CACHE.get(key) for key in keys]

        # Mixed/all-hit caches are already efficient in the mature two-pass path.
        # Fuse only the expensive case where all images are actually new.
        if any(record is not None for record in cached):
            return original(
                clip,
                prompt,
                references,
                images,
                analyzer_name=analyzer_name,
                clip_loader=clip_loader,
                max_image_edge=edge,
                deep_enhancement=deep_enhancement,
                writer_clip=writer_clip,
                writer_name=writer_name,
                writer_loader=writer_loader,
                writer_instruction=writer_instruction,
            )

        if clip is None and callable(clip_loader):
            LOGGER.info("[H3 Studio - Director] Loading shared analyzer/writer: %s", identity)
            clip = clip_loader()
        if clip is None:
            return original(
                clip,
                prompt,
                references,
                images,
                analyzer_name=analyzer_name,
                clip_loader=clip_loader,
                max_image_edge=edge,
                deep_enhancement=deep_enhancement,
                writer_clip=writer_clip,
                writer_name=writer_name,
                writer_loader=writer_loader,
                writer_instruction=writer_instruction,
            )

        prepared = [analyzer._prepare_image(image, edge) for image in images]
        expected = {int(reference.ordinal) for reference in references}
        order = "\n".join(
            f"Image {reference.ordinal}: filename={reference.filename}"
            for reference in references
        )
        custom = str(writer_instruction or "").strip()[:4000]
        instruction = (
            f"{FUSED_SYSTEM_INSTRUCTION}\n\n"
            f"USER REQUEST:\n{prompt}\n\n"
            f"REFERENCE ORDER:\n{order}\n\n"
            + (f"ADDITIONAL USER DIRECTOR GUIDANCE:\n{custom}\n\n" if custom else "")
            + f"Return exactly {len(references)} reference records using the listed ordinals and one final instruction."
        )

        started = time.perf_counter()
        LOGGER.info(
            "[H3 Studio - Director] Fused multimodal pass | %d fresh image(s) | max edge %s",
            len(prepared), "native" if edge == 0 else f"{edge}px",
        )
        records = None
        final_instruction = ""
        last_failure = ""
        for attempt in range(2):
            retry = "" if not last_failure else (
                "\n\nVALIDATION FAILED: " + last_failure
                + " Return one complete JSON object; do not omit any reference or @Image assignment."
            )
            tokens = clip.tokenize(instruction + retry, images=prepared, thinking=False)
            generated = clip.generate(
                tokens,
                do_sample=False,
                max_length=min(1800, 520 + len(prepared) * 190 + (180 if attempt else 0)),
                temperature=1.0,
                top_k=0,
                top_p=1.0,
                min_p=0.0,
                repetition_penalty=1.05,
                seed=0,
                presence_penalty=0.0,
            )
            try:
                payload = analyzer._json_object(_decoded_text(clip, generated))
                if not isinstance(payload.get("references"), list):
                    raise ValueError("fused JSON did not contain references")
                records = analyzer._validated_analysis_records(payload, expected)
                # Persist valid facts immediately. If only the writer part fails,
                # the fallback will reuse these facts instead of rerunning vision.
                with analyzer._CACHE_LOCK:
                    for index, (reference, _image) in enumerate(paired):
                        record = records.get(int(reference.ordinal))
                        if record is not None:
                            analyzer._store_analysis_record(keys[index], record)
                analyzed = analyzer._apply_payload(
                    references,
                    {"references": [records[int(reference.ordinal)] for reference in references]},
                )
                final_instruction = " ".join(str(payload.get("instruction") or "").split())
                if not final_instruction:
                    raise ValueError("fused JSON did not contain an instruction")
                failures = analyzer._writer_failures(final_instruction, str(prompt))
                if failures:
                    raise ValueError("; ".join(failures))

                facts = tuple(
                    (item.ordinal, item.effective_role, item.retention, item.description)
                    for item in analyzed
                )
                writer_identity = writer_name or identity
                writer_key = (str(writer_identity), str(prompt), facts, custom)
                elapsed = time.perf_counter() - started
                note = (
                    f"Image analysis + prompt director: fused shared-model pass inspected {len(analyzed)} fresh "
                    f"reference(s) and produced a validated {len(final_instruction.split())}-word instruction in {elapsed:.2f}s."
                )
                with analyzer._CACHE_LOCK:
                    analyzer._store_writer_result(writer_key, final_instruction, note)
                LOGGER.info(
                    "[H3 Studio - Director] Fused pass complete | %.2fs | %d words",
                    elapsed,
                    len(final_instruction.split()),
                )
                return analyzed, final_instruction, note
            except (ValueError, json.JSONDecodeError) as exc:
                last_failure = str(exc)
                LOGGER.warning(
                    "[H3 Studio - Director] Fused structured output invalid | attempt %d/2 | %s",
                    attempt + 1,
                    last_failure,
                )

        LOGGER.warning(
            "[H3 Studio - Director] Fused pass fell back to validated two-stage writer | %s",
            last_failure,
        )
        # Valid reference records, if any, were already cached above, so this
        # fallback normally pays only for the text writer rather than vision again.
        return original(
            clip,
            prompt,
            references,
            images,
            analyzer_name=analyzer_name,
            clip_loader=clip_loader,
            max_image_edge=edge,
            deep_enhancement=deep_enhancement,
            writer_clip=clip if writer_clip is None else writer_clip,
            writer_name=writer_name,
            writer_loader=writer_loader,
            writer_instruction=writer_instruction,
        )

    analyze_references.__h3studio_fused_prompt_v2__ = True
    analyzer.analyze_references = analyze_references


__all__ = ["install"]
