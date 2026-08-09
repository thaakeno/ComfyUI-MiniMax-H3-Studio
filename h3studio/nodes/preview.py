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
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)
WRAPPER_KEY = "h3studio_taeh3_preview"
DEFAULT_TAEH3 = "taeh3.safetensors"
_PREVIEW_MODEL_CACHE_LOCK = threading.RLock()
_PREVIEW_MODEL_CACHE_KEY = None
_PREVIEW_MODEL_CACHE_VALUE = None


def _conv(torch, channels_in: int, channels_out: int, *, bias: bool = True):
    return torch.nn.Conv2d(channels_in, channels_out, 3, padding=1, bias=bias)


def _block(torch, channels_in: int, channels_out: int):
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

        def forward(self, value):
            return torch.nn.functional.relu(self.conv(value) + self.skip(value))

    return Block()


def _decoder(torch):
    class Clamp(torch.nn.Module):
        def forward(self, value):
            return torch.tanh(value / 3) * 3

    return torch.nn.Sequential(
        Clamp(),
        _conv(torch, 24, 96),
        torch.nn.ReLU(inplace=True),
        _block(torch, 96, 96),
        _block(torch, 96, 96),
        _block(torch, 96, 96),
        torch.nn.Upsample(scale_factor=2),
        _conv(torch, 96, 96, bias=False),
        _block(torch, 96, 96),
        _block(torch, 96, 96),
        _block(torch, 96, 96),
        torch.nn.Upsample(scale_factor=2),
        _conv(torch, 96, 96, bias=False),
        _block(torch, 96, 64),
        _block(torch, 64, 64),
        _block(torch, 64, 64),
        torch.nn.Upsample(scale_factor=2),
        _conv(torch, 64, 64, bias=False),
        _block(torch, 64, 64),
        _block(torch, 64, 64),
        torch.nn.Upsample(scale_factor=2),
        _conv(torch, 64, 64, bias=False),
        _block(torch, 64, 64),
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
    pil_image.save(buffer, format="JPEG", quality=quality, optimize=False)
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

    def _load(self, torch, device, dtype):
        if self.decoder is None:
            import comfy.utils

            state = comfy.utils.load_torch_file(self.checkpoint_path, safe_load=True)
            decoder = _decoder(torch)
            missing, unexpected = decoder.load_state_dict(state, strict=False)
            if missing or unexpected:
                raise ValueError(
                    "The selected file is not the supported Kijai TAEH3 decoder "
                    f"(missing={len(missing)}, unexpected={len(unexpected)})."
                )
            self.decoder = decoder.eval()
        self.decoder.to(device=device, dtype=dtype)
        return self.decoder

    def _send(self, torch, step, x0, total_steps, latent_shapes, run_id):
        if step % self.every != 0 and step + 1 < total_steps:
            return
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
            },
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

        def preview_callback(step, x0, x, total_steps):
            try:
                self._send(torch, step, x0, total_steps, latent_shapes, run_id)
            except Exception as error:
                LOGGER.warning("H3 Studio TAEH3 preview skipped: %s", error)
            if callback is not None:
                callback(step, x0, x, total_steps)

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
                "max_resolution": ("INT", {"default": 512, "min": 256, "max": 1024, "step": 64}),
                "jpeg_quality": ("INT", {"default": 80, "min": 40, "max": 95, "step": 1}),
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
