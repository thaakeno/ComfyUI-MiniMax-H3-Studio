"""Optional MiniMax H3 tiny-decoder live previews.

The implementation uses ComfyUI's public sampler-wrapper and websocket APIs.
It targets Kijai's Apache-2.0 ``taeh3.safetensors`` decoder checkpoint while
remaining independent of KJNodes.
"""

from __future__ import annotations

import base64
import io
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any

LOGGER = logging.getLogger(__name__)
WRAPPER_KEY = "h3studio_taeh3_preview"
DEFAULT_TAEH3 = "taeh3.safetensors"
_PREVIEW_MODEL_CACHE_LOCK = threading.RLock()
_PREVIEW_MODEL_CACHE_KEY = None
_PREVIEW_MODEL_CACHE_VALUE = None


def _conv(torch, channels_in: int, channels_out: int, *, bias: bool = True):
    return torch.nn.Conv2d(channels_in, channels_out, 3, padding=1, bias=bias)


def _block(torch, channels_in: int, channels_out: int, *, use_midblock_gn: bool = False):
    class Block(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = torch.nn.Sequential(
                _conv(torch, channels_in, channels_out),
                torch.nn.ReLU(inplace=True),
                _conv(torch, channels_out, channels_out),
                torch.nn.ReLU(inplace=True),
                _conv(torch, channels_out, channels_out),
            )
            self.skip = (
                torch.nn.Conv2d(channels_in, channels_out, 1, bias=False)
                if channels_in != channels_out
                else torch.nn.Identity()
            )
            expanded = channels_in * 4
            self.pool = (
                torch.nn.Sequential(
                    torch.nn.Conv2d(channels_in, expanded, 1, bias=False),
                    torch.nn.GroupNorm(4, expanded),
                    torch.nn.ReLU(inplace=True),
                    torch.nn.Conv2d(expanded, channels_in, 1, bias=False),
                )
                if use_midblock_gn
                else None
            )

        def forward(self, value):
            if self.pool is not None:
                value = value + self.pool(value)
            return torch.nn.functional.relu(self.conv(value) + self.skip(value))

    return Block()


def _decoder(torch, state):
    class Clamp(torch.nn.Module):
        def forward(self, value):
            return torch.tanh(value / 3) * 3

    def block(index: int, channels_in: int, channels_out: int):
        use_midblock_gn = any(str(key).startswith(f"{index}.pool.") for key in state)
        return _block(torch, channels_in, channels_out, use_midblock_gn=use_midblock_gn)

    return torch.nn.Sequential(
        Clamp(),
        _conv(torch, 24, 96),
        torch.nn.ReLU(inplace=True),
        block(3, 96, 96),
        block(4, 96, 96),
        block(5, 96, 96),
        torch.nn.Upsample(scale_factor=2),
        _conv(torch, 96, 96, bias=False),
        block(8, 96, 96),
        block(9, 96, 96),
        block(10, 96, 96),
        torch.nn.Upsample(scale_factor=2),
        _conv(torch, 96, 96, bias=False),
        block(13, 96, 64),
        block(14, 64, 64),
        block(15, 64, 64),
        torch.nn.Upsample(scale_factor=2),
        _conv(torch, 64, 64, bias=False),
        block(18, 64, 64),
        block(19, 64, 64),
        torch.nn.Upsample(scale_factor=2),
        _conv(torch, 64, 64, bias=False),
        block(22, 64, 64),
        _conv(torch, 64, 3),
    )


def _vae_choices() -> list[str]:
    import folder_paths

    try:
        choices = list(folder_paths.get_filename_list("vae_approx"))
    except Exception:
        choices = []
    if DEFAULT_TAEH3 not in choices:
        choices.insert(0, DEFAULT_TAEH3)
    return choices


def _resolve_packed_latent(torch, value, latent_shapes):
    """Restore Comfy's packed multi-latent tensor when shape metadata is present."""

    if getattr(value, "ndim", 0) != 3 or not latent_shapes:
        return value
    shape = tuple(int(part) for part in latent_shapes[0])
    required = math.prod(shape[1:])
    flattened = value.reshape(value.shape[0], -1)
    if flattened.shape[1] < required:
        raise ValueError(f"Packed latent has {flattened.shape[1]} values; H3 shape requires {required}.")
    return flattened[:, :required].reshape((value.shape[0], *shape[1:]))


def _first_h3_latent(torch, value, latent_shapes):
    value = _resolve_packed_latent(torch, value, latent_shapes)
    if value.ndim == 5:
        return value[:, :, 0]
    if value.ndim == 4:
        return value
    raise ValueError(f"Expected a four- or five-dimensional H3 latent, got shape {tuple(value.shape)}.")


def _limit_latent(torch, value, max_resolution: int):
    output_height, output_width = value.shape[-2] * 16, value.shape[-1] * 16
    longest = max(output_height, output_width)
    if longest <= max_resolution:
        return value
    scale = max_resolution / longest
    latent_height = max(1, round(value.shape[-2] * scale))
    latent_width = max(1, round(value.shape[-1] * scale))
    return torch.nn.functional.interpolate(
        value, size=(latent_height, latent_width), mode="bilinear", align_corners=False
    )


def _jpeg_data_url(torch, image, quality: int) -> tuple[str, int, int]:
    from PIL import Image

    pixels = image[0].detach().float().clamp(0, 1).mul(255).byte().permute(1, 2, 0).cpu().numpy()
    pil_image = Image.fromarray(pixels, mode="RGB")
    buffer = io.BytesIO()
    pil_image.save(buffer, format="JPEG", quality=quality, subsampling=0, optimize=False)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}", pil_image.width, pil_image.height


@dataclass
class _PreviewWrapper:
    checkpoint_path: str
    node_id: str
    max_resolution: int
    jpeg_quality: int
    every: int
    decoder: Any = None
    run_serial: int = 0
    _worker_lock: Any = field(default_factory=threading.Lock, repr=False)
    _worker: Any = field(default=None, repr=False)
    _pending: Any = field(default=None, repr=False)

    def _load(self, torch, device, dtype):
        if self.decoder is None:
            import comfy.utils

            state = comfy.utils.load_torch_file(self.checkpoint_path, safe_load=True)
            decoder = _decoder(torch, state)
            decoder.load_state_dict(state, strict=True)
            self.decoder = decoder.eval()
        self.decoder.to(device=device, dtype=dtype)
        return self.decoder

    def _send(self, torch, step, x0, total_steps, latent_shapes, run_id, elapsed_seconds, average_step_seconds):
        latent = _limit_latent(torch, _first_h3_latent(torch, x0, latent_shapes), self.max_resolution)
        decoder = self._load(torch, latent.device, latent.dtype)
        with torch.inference_mode():
            image = decoder(latent).clamp(0, 1)
        data_url, width, height = _jpeg_data_url(torch, image, self.jpeg_quality)
        from server import PromptServer

        server = PromptServer.instance
        server.send_sync(
            "h3studio-preview",
            {
                "node_id": self.node_id,
                "image": data_url,
                "step": int(step) + 1,
                "total": int(total_steps),
                "width": width,
                "height": height,
                "run_id": run_id,
                "elapsed_seconds": float(elapsed_seconds),
                "average_step_seconds": float(average_step_seconds),
                "eta_seconds": max(0.0, float(average_step_seconds) * (int(total_steps) - int(step) - 1)),
            },
            server.client_id,
        )

    def _worker_loop(self, torch):
        while True:
            with self._worker_lock:
                pending = self._pending
                self._pending = None
                if pending is None:
                    self._worker = None
                    return
            try:
                self._send(torch, *pending)
            except Exception as error:
                LOGGER.warning("H3 Studio TAEH3 preview skipped: %s", error)

    def _enqueue(self, torch, step, x0, total_steps, latent_shapes, run_id, elapsed_seconds, average_step_seconds):
        if step % self.every != 0 and step + 1 < total_steps:
            return
        snapshot = x0.detach().clone()
        with self._worker_lock:
            self._pending = (
                step,
                snapshot,
                total_steps,
                latent_shapes,
                run_id,
                elapsed_seconds,
                average_step_seconds,
            )
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._worker_loop, args=(torch,), daemon=True)
                self._worker.start()

    def _reset_frontend(self, total_steps: int, run_id: str):
        from server import PromptServer

        server = PromptServer.instance
        server.send_sync(
            "h3studio-preview",
            {"node_id": self.node_id, "run_id": run_id, "total": int(total_steps), "reset": True},
            server.client_id,
        )

    def __call__(self, executor, *args, **kwargs):
        import torch

        self.run_serial += 1
        run_id = f"{self.node_id}:{self.run_serial}"
        positional = list(args)
        callback = kwargs.get("callback")
        callback_index = None
        if callback is None and len(positional) > 5:
            callback_index = 5
            callback = positional[callback_index]
        latent_shapes = kwargs.get("latent_shapes", positional[8] if len(positional) > 8 else None)
        total_steps = len(positional[3]) - 1 if len(positional) > 3 and hasattr(positional[3], "__len__") else 0
        sampling_started = time.perf_counter()
        try:
            self._reset_frontend(total_steps, run_id)
        except Exception as error:
            LOGGER.debug("H3 Studio preview reset event skipped: %s", error)

        def preview_callback(step, x0, x, total_steps):
            if callback is not None:
                callback(step, x0, x, total_steps)
            try:
                elapsed_seconds = time.perf_counter() - sampling_started
                completed_steps = max(1, int(step) + 1)
                self._enqueue(
                    torch,
                    step,
                    x0,
                    total_steps,
                    latent_shapes,
                    run_id,
                    elapsed_seconds,
                    elapsed_seconds / completed_steps,
                )
            except Exception as error:
                LOGGER.warning("H3 Studio TAEH3 preview enqueue skipped: %s", error)

        if callback_index is None:
            kwargs["callback"] = preview_callback
        else:
            positional[callback_index] = preview_callback
        # A Comfy wrapper must call the executor object so it advances to the
        # next wrapper. Calling executor.execute() restarts the current index
        # and recursively invokes this same wrapper until Python overflows.
        return executor(*positional, **kwargs)


class H3StudioTAEH3Preview:
    """Attach fast approximate H3 live previews to a model clone."""

    CATEGORY = "H3 Studio/Preview"
    FUNCTION = "attach"
    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("model",)
    DESCRIPTION = "Fast approximate live previews only. Final output still uses the connected full H3 VAE."
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "enabled": ("BOOLEAN", {"default": False}),
                "tiny_vae": (_vae_choices(), {"default": DEFAULT_TAEH3}),
                "max_resolution": ("INT", {"default": 768, "min": 256, "max": 1024, "step": 64}),
                "jpeg_quality": ("INT", {"default": 90, "min": 40, "max": 95, "step": 1}),
                "preview_every_n_steps": ("INT", {"default": 1, "min": 1, "max": 20, "step": 1}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    @staticmethod
    def attach(model, enabled, tiny_vae, max_resolution, jpeg_quality, preview_every_n_steps, unique_id=None):
        global _PREVIEW_MODEL_CACHE_KEY, _PREVIEW_MODEL_CACHE_VALUE
        if not enabled:
            with _PREVIEW_MODEL_CACHE_LOCK:
                _PREVIEW_MODEL_CACHE_KEY = None
                _PREVIEW_MODEL_CACHE_VALUE = None
            return (model,)

        import comfy.patcher_extension
        import folder_paths

        checkpoint_path = folder_paths.get_full_path("vae_approx", tiny_vae)
        if not checkpoint_path:
            raise FileNotFoundError(
                f"TAEH3 preview file '{tiny_vae}' was not found. Put it in ComfyUI/models/vae_approx/."
            )
        cache_key = (
            id(model),
            checkpoint_path,
            str(unique_id or ""),
            int(max_resolution),
            int(jpeg_quality),
            max(1, int(preview_every_n_steps)),
        )
        with _PREVIEW_MODEL_CACHE_LOCK:
            if cache_key == _PREVIEW_MODEL_CACHE_KEY and _PREVIEW_MODEL_CACHE_VALUE is not None:
                LOGGER.info("[H3 Studio] TAEH3 wrapper cache hit; reused the single preview-enabled model")
                return (_PREVIEW_MODEL_CACHE_VALUE,)
            patched = model.clone()
            patched.remove_wrappers_with_key(comfy.patcher_extension.WrappersMP.OUTER_SAMPLE, WRAPPER_KEY)
            patched.add_wrapper_with_key(
                comfy.patcher_extension.WrappersMP.OUTER_SAMPLE,
                WRAPPER_KEY,
                _PreviewWrapper(
                    checkpoint_path=checkpoint_path,
                    node_id=str(unique_id or ""),
                    max_resolution=int(max_resolution),
                    jpeg_quality=int(jpeg_quality),
                    every=max(1, int(preview_every_n_steps)),
                ),
            )
            _PREVIEW_MODEL_CACHE_KEY = cache_key
            _PREVIEW_MODEL_CACHE_VALUE = patched
            return (patched,)
