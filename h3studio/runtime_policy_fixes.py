"""Runtime policy corrections discovered from real L4 traces.

The public runtime node remains unchanged.  This install layer fixes two things:
* PackedLayout compatibility across ComfyUI H3 revisions.
* Fast means an actual speed-oriented backend; it no longer silently falls back
  to the memory-efficient Sage path used by Low/Extreme VRAM modes.
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from typing import Any

from .runtime_optimization import (
    ATTENTION_CK,
    ATTENTION_PYTORCH,
    ATTENTION_SAGE,
    RuntimeDecision,
)


def _packed_sequence_compat(samples: Any, conditioning: Any) -> tuple[int, str]:
    try:
        from comfy.ldm.minimax.model import PackedLayout

        latent = samples["samples"]
        if getattr(latent, "is_nested", False):
            values = latent.unbind()
            video = values[0]
            audio_t = int(values[1].shape[-1]) if len(values) > 1 else 0
        else:
            video = latent
            audio_t = 0
        if video.ndim != 5:
            return 0, f"unavailable: unexpected latent shape {tuple(video.shape)}"

        latent_t = int(video.shape[2])
        lat_h = (int(video.shape[3]) + 1) // 2 * 2
        lat_w = (int(video.shape[4]) + 1) // 2 * 2
        try:
            parameters = inspect.signature(PackedLayout).parameters
        except Exception:
            parameters = {}

        layouts = []
        for cond, cond_dict in conditioning:
            kwargs = {
                "keyframes": cond_dict.get("minimax_keyframes"),
                "refs": cond_dict.get("minimax_refs"),
            }
            if "frame_count" in parameters:
                kwargs["frame_count"] = cond_dict.get("minimax_frame_count")
            try:
                layout = PackedLayout(
                    int(cond.shape[1]), latent_t, lat_h, lat_w, audio_t, **kwargs
                )
            except TypeError as exc:
                # Some upstream revisions accepted keyframes/refs but not the
                # newer frame_count argument. Retry the minimal compatible form.
                if "frame_count" not in str(exc):
                    raise
                kwargs.pop("frame_count", None)
                layout = PackedLayout(
                    int(cond.shape[1]), latent_t, lat_h, lat_w, audio_t, **kwargs
                )
            layouts.append(layout)

        if not layouts:
            return 0, "unavailable: empty conditioning"
        layout = max(layouts, key=lambda item: item.seq_len)
        rows: dict[str, int] = {}
        blocks: dict[str, int] = {}
        for start, stop, kind in layout.segments:
            rows[kind] = rows.get(kind, 0) + int(stop - start)
            blocks[kind] = blocks.get(kind, 0) + 1
        details = [
            f"total={layout.seq_len}",
            f"text={rows.get('text', 0)}",
            f"video={rows.get('video', 0)}",
        ]
        if rows.get("audio"):
            details.append(f"audio={rows['audio']}")
        if rows.get("cond"):
            details.append(f"keyframes={rows['cond']}({blocks.get('cond', 0)})")
        if rows.get("ref_img"):
            details.append(f"image_refs={rows['ref_img']}({blocks.get('ref_img', 0)})")
        if rows.get("ref_audio"):
            details.append(f"audio_refs={rows['ref_audio']}({blocks.get('ref_audio', 0)})")
        return int(layout.seq_len), " · ".join(details)
    except Exception as exc:
        return 0, f"unavailable: {type(exc).__name__}: {exc}"


def _truthful_runtime_resolver(original):
    def resolve(requested, caps, workload, advanced=None):
        decision: RuntimeDecision = original(requested, caps, workload, advanced)
        request = str(decision.requested)

        # Fast is a speed mode.  Sage H3 is retained for memory-saving modes;
        # using it as Fast's fallback made Fast/Low/Extreme nearly identical on
        # the L4 and made the UI claim a speed path that was not being executed.
        if request == "fast" or (request == "auto" and decision.resolved == "fast"):
            if getattr(caps, "ck_attention", False):
                backend = ATTENTION_CK
                fallback = tuple(
                    item for item in decision.fallbacks
                    if "SageAttention" not in str(item)
                )
            else:
                backend = ATTENTION_PYTORCH
                fallback = (
                    "Comfy Kitchen INT8 is unavailable; Fast uses PyTorch rather than the low-memory Sage path.",
                )
            decision = replace(
                decision,
                attention_backend=backend,
                head_chunks=1,
                fallbacks=fallback,
                reason=(
                    "Speed-oriented H3 path: use Comfy Kitchen INT8 with no head chunking."
                    if backend == ATTENTION_CK
                    else "Speed-oriented fallback: use unchunked PyTorch attention because Comfy Kitchen INT8 is unavailable."
                ),
            )

        # Keep the memory presets semantically distinct even when the host has
        # plenty of VRAM. These are survival/peak-memory modes, not speed modes.
        elif request in {"low_vram", "extreme_low_vram"}:
            if getattr(caps, "sage_mem_eff", False):
                chunks = 2 if request == "low_vram" else max(4, int(decision.head_chunks))
                decision = replace(
                    decision,
                    attention_backend=ATTENTION_SAGE,
                    head_chunks=chunks if getattr(caps, "low_vram_attention", False) else 1,
                    reason=(
                        "Memory-saving H3 path: SageAttention with two exact head groups to reduce transient VRAM."
                        if request == "low_vram"
                        else "Last-resort H3 memory path: SageAttention with aggressive exact head grouping; slower is expected."
                    ),
                )
        return decision

    resolve.__h3studio_truthful_runtime_v2__ = True
    return resolve


def install() -> None:
    from .nodes import runtime as runtime_nodes

    runtime_nodes._packed_sequence = _packed_sequence_compat
    current = runtime_nodes.resolve_runtime
    if not bool(getattr(current, "__h3studio_truthful_runtime_v2__", False)):
        runtime_nodes.resolve_runtime = _truthful_runtime_resolver(current)


__all__ = ["install"]
