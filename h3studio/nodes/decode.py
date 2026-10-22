"""Native MiniMax H3 VAE decode controls, batching and live tile progress.

This module configures the H3 VAE instance that ComfyUI already owns. It never
loads a second decoder or replaces H3 weights. During one decode call it installs
a narrow instance-scoped spatial tile adapter, then restores the original model
attributes/method in ``finally``.
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from types import MethodType
from typing import Any

import comfy.model_management
import comfy.utils
import torch

from ..host_memory import relieve_host_memory_pressure
from ..runtime_trace import span
from ..vae_io import detect_vae_io
from .image_runtime import CATEGORY, _first_stable_edit_frame

LOGGER = logging.getLogger(__name__)
GIB = 1024**3
_NATIVE_TILE = 256
_NATIVE_OVERLAP = 64
_ADAPTER_LOCK = threading.RLock()


def _aligned(value: int, alignment: int, *, minimum: int) -> int:
    alignment = max(1, int(alignment))
    value = max(int(minimum), int(value))
    return max(minimum, int(round(value / alignment)) * alignment)


def _resolve_spatial_settings(model: Any, mode: str, tile_size: int, overlap: int) -> tuple[int, int]:
    ratio = max(1, int(getattr(model, "vae_ratio", 16) or 16))
    if str(mode).lower() != "manual":
        return _NATIVE_TILE, _NATIVE_OVERLAP

    tile = _aligned(tile_size, ratio, minimum=ratio * 8)
    tile = max(ratio * 2, tile)
    overlap_value = _aligned(overlap, ratio, minimum=ratio)
    overlap_value = min(overlap_value, tile - ratio)
    return tile, overlap_value


def _spatial_grid(model: Any, latent: torch.Tensor) -> tuple[int, int, int]:
    ratio = max(1, int(getattr(model, "vae_ratio", 16) or 16))
    height = int(latent.shape[-2]) * ratio
    width = int(latent.shape[-1]) * ratio
    y_idx, _y_len, _y_overlap = model.split_tiles(height)
    x_idx, _x_len, _x_overlap = model.split_tiles(width)
    return len(y_idx), len(x_idx), len(y_idx) * len(x_idx)


def _temporal_decode_passes(model: Any, latent: torch.Tensor) -> int:
    if latent.ndim < 5 or int(latent.shape[2]) <= 1:
        return 1
    planner = getattr(model, "_decode_temporal_chunks", None)
    if callable(planner):
        with suppress(Exception):
            _pad, count = planner(int(latent.shape[2]))
            return max(1, int(count))
    return 1


def _free_vram_bytes() -> int:
    try:
        if torch.cuda.is_available():
            free, _total = torch.cuda.mem_get_info(torch.cuda.current_device())
            return max(0, int(free))
    except Exception:
        pass
    return 0


def _requested_batch_cap(value: str | int) -> int | None:
    if str(value).strip().lower() == "auto":
        return None
    try:
        return max(1, min(4, int(value)))
    except (TypeError, ValueError):
        return 1


def _auto_batch_cap(tile_count: int) -> int:
    if tile_count <= 1:
        return 1
    free = _free_vram_bytes()
    if free >= 14 * GIB and tile_count >= 4:
        return 4
    if free >= 7 * GIB and tile_count >= 2:
        return 2
    return 1


def _send_status(node_id: str | int | None, payload: dict[str, Any]) -> None:
    if node_id is None:
        return
    try:
        from server import PromptServer

        instance = getattr(PromptServer, "instance", None)
        if instance is not None:
            instance.send_sync("h3studio.decode_status", {"node": str(node_id), **payload})
    except Exception:
        pass


@dataclass
class _TileProgress:
    node_id: str | int | None
    total: int
    tile_size: int
    overlap: int
    grid_y: int
    grid_x: int
    batch_setting: str

    def __post_init__(self) -> None:
        self.total = max(1, int(self.total))
        self.completed = 0
        self.started = time.monotonic()
        self.last_event = 0.0
        self.max_batch_used = 1
        self.batch_cap_after_oom: int | None = None
        try:
            self.pbar = comfy.utils.ProgressBar(self.total, node_id=self.node_id)
        except TypeError:
            self.pbar = comfy.utils.ProgressBar(self.total)

    def batch_cap(self, remaining: int) -> int:
        requested = _requested_batch_cap(self.batch_setting)
        cap = requested if requested is not None else _auto_batch_cap(remaining)
        if self.batch_cap_after_oom is not None:
            cap = min(cap, self.batch_cap_after_oom)
        return max(1, min(int(cap), int(remaining)))

    def note_oom(self, attempted: int) -> None:
        self.batch_cap_after_oom = max(1, int(attempted) // 2)

    def update(self, count: int) -> None:
        count = max(0, int(count))
        self.completed = min(self.total, self.completed + count)
        with suppress(Exception):
            self.pbar.update(count)
        comfy.model_management.throw_exception_if_processing_interrupted()
        self.emit(force=self.completed >= self.total)

    def emit(self, *, force: bool = False, status: str = "decoding", error: str | None = None) -> None:
        now = time.monotonic()
        if not force and now - self.last_event < 0.15:
            return
        self.last_event = now
        elapsed = max(0.0, now - self.started)
        payload = {
            "status": status,
            "completed": self.completed,
            "total": self.total,
            "percent": round(self.completed * 100 / max(1, self.total), 1),
            "grid": f"{self.grid_x} × {self.grid_y}",
            "grid_x": self.grid_x,
            "grid_y": self.grid_y,
            "tile_size": self.tile_size,
            "overlap": self.overlap,
            "batch": self.max_batch_used,
            "batch_setting": self.batch_setting,
            "elapsed": round(elapsed, 2),
        }
        if error:
            payload["error"] = error
        _send_status(self.node_id, payload)


def _decode_group(model: Any, latent_tiles: list[torch.Tensor], progress: _TileProgress) -> list[torch.Tensor]:
    """Decode equal-shaped spatial tiles in one native H3 forward with OOM backoff."""

    count = len(latent_tiles)
    if count <= 0:
        return []
    if count == 1:
        output = model._decode_pixels(latent_tiles[0])
        progress.max_batch_used = max(progress.max_batch_used, 1)
        return [output]

    shape = tuple(latent_tiles[0].shape)
    if any(tuple(tile.shape) != shape for tile in latent_tiles[1:]):
        result: list[torch.Tensor] = []
        for tile in latent_tiles:
            result.extend(_decode_group(model, [tile], progress))
        return result

    base_batch = int(shape[0])
    retry = False
    try:
        combined = torch.cat(latent_tiles, dim=0)
        decoded = model._decode_pixels(combined)
        outputs = list(decoded.split(base_batch, dim=0))
        if len(outputs) != count:
            raise RuntimeError(f"H3 tile batch split mismatch: expected {count}, got {len(outputs)}")
        progress.max_batch_used = max(progress.max_batch_used, count)
        return outputs
    except Exception as error:
        if not comfy.model_management.is_oom(error) or count <= 1:
            raise
        progress.note_oom(count)
        LOGGER.warning(
            "[H3 Studio - Decode] Native tile batch %d exceeded VRAM; backing off to %d.",
            count,
            max(1, count // 2),
        )
        retry = True

    if retry:
        comfy.model_management.soft_empty_cache()
        midpoint = max(1, count // 2)
        left = _decode_group(model, latent_tiles[:midpoint], progress)
        right = _decode_group(model, latent_tiles[midpoint:], progress)
        return left + right
    raise AssertionError("unreachable H3 tile batch state")


def _batched_tiled_decode(model: Any, z: torch.Tensor, progress: _TileProgress) -> torch.Tensor:
    """Native H3 spatial decode with the upstream blend geometry and batched forwards."""

    ratio = int(model.vae_ratio)
    height, width = int(z.shape[-2]) * ratio, int(z.shape[-1]) * ratio
    y_idx, y_len, y_overlap = model.split_tiles(height)
    x_idx, x_len, x_overlap = model.split_tiles(width)

    canvas = None
    row_tails: list[torch.Tensor] = []
    out_y = 0

    for row_index, (y_pos, y_size) in enumerate(zip(y_idx, y_len, strict=False)):
        zi, zl = y_pos // ratio, y_size // ratio
        specs = []
        for col_index, (x_pos, x_size) in enumerate(zip(x_idx, x_len, strict=False)):
            zj, zw = x_pos // ratio, x_size // ratio
            specs.append((col_index, z[..., zi : zi + zl, zj : zj + zw]))

        decoded_row: list[torch.Tensor] = []
        cursor = 0
        while cursor < len(specs):
            remaining = len(specs) - cursor
            batch_cap = progress.batch_cap(remaining)
            group = [tile for _col, tile in specs[cursor : cursor + batch_cap]]
            decoded_group = _decode_group(model, group, progress)
            decoded_row.extend(decoded_group)
            progress.update(len(decoded_group))
            cursor += len(decoded_group)

        new_tails: list[torch.Tensor] = []
        left_tail = None
        out_x = 0
        last_height = 0
        for col_index, tile in enumerate(decoded_row):
            if row_index < len(y_idx) - 1:
                new_tails.append(tile[..., -y_overlap[row_index] :, :].clone())
            next_left_tail = (
                tile[..., :, -x_overlap[col_index] :].clone()
                if col_index < len(x_idx) - 1
                else None
            )

            if row_index > 0:
                tile = model.blend(row_tails[col_index], tile, y_overlap[row_index - 1], dim=-2)
            if col_index > 0:
                tile = model.blend(left_tail, tile, x_overlap[col_index - 1], dim=-1)
            left_tail = next_left_tail

            if row_index < len(y_idx) - 1:
                tile = tile[..., : -y_overlap[row_index], :]
            if col_index < len(x_idx) - 1:
                tile = tile[..., :, : -x_overlap[col_index]]

            if canvas is None:
                canvas = torch.empty(
                    *tile.shape[:-2],
                    height,
                    width,
                    dtype=tile.dtype,
                    device=tile.device,
                )
            canvas[
                ...,
                out_y : out_y + tile.shape[-2],
                out_x : out_x + tile.shape[-1],
            ].copy_(tile)
            out_x += int(tile.shape[-1])
            last_height = int(tile.shape[-2])

        row_tails = new_tails
        out_y += last_height

    if canvas is None:
        raise RuntimeError("H3 native tile decoder produced no spatial tiles")
    return canvas


@contextmanager
def _native_decode_adapter(
    model: Any,
    *,
    tile_size: int,
    overlap: int,
    progress: _TileProgress,
):
    """Temporarily configure one H3 VAE instance and restore it exactly."""

    if not all(hasattr(model, name) for name in ("tile_size", "tile_overlap_min", "tiling", "split_tiles", "blend")):
        yield False
        return

    with _ADAPTER_LOCK:
        previous_tile = model.tile_size
        previous_overlap = model.tile_overlap_min
        previous_tiling = model.tiling
        had_instance_method = "tiled_decode" in getattr(model, "__dict__", {})
        previous_instance_method = getattr(model, "__dict__", {}).get("tiled_decode")

        def adapter(instance, z, frames=slice(None)):
            return _batched_tiled_decode(instance, z, progress)[:, :, frames]

        try:
            model.tile_size = int(tile_size)
            model.tile_overlap_min = int(overlap)
            model.tiling = True
            model.tiled_decode = MethodType(adapter, model)
            yield True
        finally:
            model.tile_size = previous_tile
            model.tile_overlap_min = previous_overlap
            model.tiling = previous_tiling
            if had_instance_method:
                model.tiled_decode = previous_instance_method
            else:
                with suppress(AttributeError):
                    delattr(model, "tiled_decode")


def _flatten_kept_frames(kept: torch.Tensor, natural_frames: int, kept_frames: int) -> torch.Tensor:
    flattened = kept.reshape(-1, *kept.shape[-3:])
    if kept_frames < natural_frames:
        return flattened.clone()
    return flattened


class H3StudioDecode:
    """Decode MiniMax H3 with configurable native spatial tiling and live progress."""

    DESCRIPTION = (
        "Decodes with the real MiniMax H3 video VAE. Auto preserves the current 256/64 native spatial context and "
        "automatically batches equal native tiles when VRAM permits, with OOM backoff. Manual exposes tile size, "
        "overlap and tile batching for 4MP/8MP tuning. The complete requested temporal profile is preserved."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": (
                    "LATENT",
                    {"tooltip": "Sampled H3 latent including Studio temporal-profile metadata."},
                ),
                "vae": (
                    "VAE",
                    {"tooltip": "The native MiniMax H3 video VAE. No approximate decoder is used."},
                ),
            },
            "optional": {
                "tiling_mode": (
                    ["Auto", "Manual"],
                    {
                        "default": "Auto",
                        "tooltip": (
                            "Auto keeps H3's compatibility tile geometry (256/64) and optimizes tile batching only. "
                            "Manual enables custom native tile geometry."
                        ),
                    },
                ),
                "tile_size": (
                    "INT",
                    {
                        "default": 256,
                        "min": 128,
                        "max": 1024,
                        "step": 16,
                        "tooltip": (
                            "Manual native spatial tile size in decoded pixels. 256 exactly matches current H3 behavior; "
                            "320/384/512 are intended for high-resolution benchmarking."
                        ),
                    },
                ),
                "tile_overlap": (
                    "INT",
                    {
                        "default": 64,
                        "min": 16,
                        "max": 512,
                        "step": 16,
                        "tooltip": "Manual minimum overlap in decoded pixels. 64 is the compatibility value.",
                    },
                ),
                "tile_batch": (
                    ["Auto", "1", "2", "4"],
                    {
                        "default": "Auto",
                        "tooltip": (
                            "Number of equal spatial tiles decoded in one native H3 forward. Auto uses free VRAM and "
                            "backs off automatically on OOM."
                        ),
                    },
                ),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("IMAGE", "INT", "STRING", "INT")
    RETURN_NAMES = ("frames", "decoded_frames", "decode_info", "recommended_index")
    OUTPUT_TOOLTIPS = (
        "Complete decoded profile(s), flattened batch-major for standard ComfyUI IMAGE output.",
        "Total number of emitted images across all batch items.",
        "Native tile plan, live-work summary and preferred-frame diagnostics.",
        "Preferred zero-based still index for the first batch item. Connect it to Single Image Output.",
    )
    FUNCTION = "decode"
    CATEGORY = CATEGORY

    def decode(
        self,
        samples,
        vae,
        tiling_mode: str = "Auto",
        tile_size: int = 256,
        tile_overlap: int = 64,
        tile_batch: str = "Auto",
        unique_id=None,
    ):
        latent = samples["samples"]
        if latent.is_nested:
            latent = latent.unbind()[0]

        latent_batch = int(latent.shape[0]) if hasattr(latent, "shape") and len(latent.shape) > 0 else 1
        first_stage = getattr(vae, "first_stage_model", None)
        supported = first_stage is not None and all(
            hasattr(first_stage, name)
            for name in ("tile_size", "tile_overlap_min", "tiling", "split_tiles", "_decode_pixels")
        )

        resolved_tile = _NATIVE_TILE
        resolved_overlap = _NATIVE_OVERLAP
        grid_y = grid_x = spatial_tiles = 1
        temporal_passes = 1
        if supported:
            resolved_tile, resolved_overlap = _resolve_spatial_settings(
                first_stage,
                tiling_mode,
                tile_size,
                tile_overlap,
            )
            previous_tile, previous_overlap = first_stage.tile_size, first_stage.tile_overlap_min
            try:
                first_stage.tile_size = resolved_tile
                first_stage.tile_overlap_min = resolved_overlap
                grid_y, grid_x, spatial_tiles = _spatial_grid(first_stage, latent)
            finally:
                first_stage.tile_size = previous_tile
                first_stage.tile_overlap_min = previous_overlap
            temporal_passes = _temporal_decode_passes(first_stage, latent)

        total_tile_work = max(1, spatial_tiles * temporal_passes)
        progress = _TileProgress(
            unique_id,
            total_tile_work,
            resolved_tile,
            resolved_overlap,
            grid_y,
            grid_x,
            str(tile_batch),
        )
        progress.emit(force=True, status="starting")

        relieve_host_memory_pressure("vae.decode.prepare", logger=LOGGER)
        decode_started = time.perf_counter()
        try:
            with span("vae.decode", state=True, patcher=getattr(vae, "patcher", None)) as result:
                if supported:
                    with _native_decode_adapter(
                        first_stage,
                        tile_size=resolved_tile,
                        overlap=resolved_overlap,
                        progress=progress,
                    ):
                        images = vae.decode(latent)
                else:
                    images = vae.decode(latent)
                result.update(output_shape=tuple(getattr(images, "shape", ())))
        except Exception as error:
            progress.emit(force=True, status="error", error=f"{type(error).__name__}: {error}")
            raise

        decode_seconds = time.perf_counter() - decode_started
        vae_io = detect_vae_io(vae)

        profile_frames = max(
            1,
            int(samples.get("h3_context_frames", samples.get("h3_requested_frames", 1))),
        )
        output_strategy = str(samples.get("h3_output_strategy", "fixed"))

        if images.ndim == 5:
            batched = images
        elif images.ndim == 4 and latent_batch > 1 and int(images.shape[0]) % latent_batch == 0:
            frames_per_item = int(images.shape[0]) // latent_batch
            batched = images.reshape(latent_batch, frames_per_item, *images.shape[-3:])
        else:
            batched = images.unsqueeze(0)

        batch_size = int(batched.shape[0])
        natural_frames = int(batched.shape[1])
        kept_frames = min(profile_frames, natural_frames)
        kept = batched[:, :kept_frames]

        preferred_indices: list[int] = []
        change_scores: list[float] = []
        fixed_index = max(0, int(samples.get("h3_output_frame_index", 0)))
        for batch_index in range(batch_size):
            item = kept[batch_index]
            if output_strategy == "first_stable_edit":
                preferred_index, change_score = _first_stable_edit_frame(item)
            else:
                preferred_index, change_score = fixed_index, 0.0
            preferred_index = min(max(0, int(preferred_index)), kept_frames - 1)
            preferred_indices.append(preferred_index)
            change_scores.append(float(change_score))

        images_out = _flatten_kept_frames(kept, natural_frames, kept_frames)
        decoded_frames = int(images_out.shape[0])

        if natural_frames == kept_frames:
            packet_note = f"Decoded the complete natural {natural_frames}-frame packet per batch item."
        else:
            packet_note = (
                f"The temporal latent naturally decoded {natural_frames} frames per batch item; kept the requested "
                f"{kept_frames}-frame profile for each item."
            )

        preferred_text = ", ".join(
            f"b{index}:frame {preferred_indices[index]} (change {change_scores[index]:.4f})"
            for index in range(batch_size)
        )
        mode_note = "Auto compatibility geometry" if str(tiling_mode).lower() != "manual" else "Manual geometry"
        batch_note = f"{tile_batch}→{progress.max_batch_used}" if supported else "native fallback"
        plan_note = (
            f"{mode_note}; tile={resolved_tile}; overlap={resolved_overlap}; grid={grid_x}x{grid_y}; "
            f"spatial_tiles={spatial_tiles}; temporal_passes={temporal_passes}; tile_batch={batch_note}"
        )
        info = (
            f"{packet_note} Batch items={batch_size}; emitted images={decoded_frames}. "
            f"Preferred still(s) via {output_strategy}: {preferred_text}. Native H3 VAE plan: {plan_note}. "
            f"No requested profile frames were discarded before Single Image Output. VAE I/O: {vae_io.label}; "
            f"decode={decode_seconds:.2f}s."
        )
        LOGGER.info(
            "[H3 Studio - Decode] %s | batch=%d | natural=%d | kept=%d | %s | %.2fs",
            vae_io.label,
            batch_size,
            natural_frames,
            kept_frames,
            plan_note,
            decode_seconds,
        )
        # Automatic Face Refinement pass if enabled in Director / samples metadata
        face_refine_mode = str(samples.get("h3_face_refine_mode", "off")).lower() if isinstance(samples, dict) else "off"
        if face_refine_mode in ("auto", "strong"):
            try:
                from ..face_refine import FaceRefineConfig, H3FaceRefinePipeline
                from .face_refine_node import build_h3_face_sampler

                fr_config = FaceRefineConfig(
                    mode=face_refine_mode,
                    crop_factor=float(samples.get("h3_face_refine_crop_factor", 2.5)),
                    guide_size=int(samples.get("h3_face_refine_guide_size", 768)),
                    denoise=float(samples.get("h3_face_refine_denoise", 0.22)),
                )
                fr_pipeline = H3FaceRefinePipeline()
                sampler_fn = build_h3_face_sampler(
                    h3_bundle=samples.get("h3_bundle") if isinstance(samples, dict) else None,
                    model=samples.get("h3_model") if isinstance(samples, dict) else None,
                    vae=vae,
                    clip=samples.get("h3_clip") if isinstance(samples, dict) else None,
                    prompt=str(samples.get("h3_prompt", "")) if isinstance(samples, dict) else "",
                )
                refine_result = fr_pipeline.refine_image(images_out, fr_config, sampler_fn=sampler_fn)
                if refine_result.faces_refined > 0:
                    images_out = refine_result.image
                    LOGGER.info("[H3 Studio - Decode] Face Refine post-processing: %s", refine_result.status_message)
                    info += f" Face Refine: {refine_result.status_message}"
            except Exception as ex:
                LOGGER.warning("[H3 Studio - Decode] Face Refine post-process failed gracefully: %s", ex)

        progress.completed = progress.total
        progress.emit(force=True, status="done")
        return images_out, decoded_frames, info, preferred_indices[0]


NODE_CLASS_MAPPINGS = {"H3StudioDecode": H3StudioDecode}
NODE_DISPLAY_NAME_MAPPINGS = {"H3StudioDecode": "H3 Studio • Native H3 VAE Decode"}

__all__ = [
    "H3StudioDecode",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "_flatten_kept_frames",
    "_resolve_spatial_settings",
]
