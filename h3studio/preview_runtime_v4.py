"""Responsive L4-safe H3 TAEH3 previews.

The decoder stays on CPU. The sampler only reshapes/downscales the tiny latent
on CUDA, copies that small tensor to CPU, and keeps at most one waiting preview.
If CPU decode falls behind, stale frames are discarded so the UI follows the
newest denoise state instead of getting stuck on step 2 while sampling advances.
"""

from __future__ import annotations

import logging
import queue
import threading
import time

from .preview_runtime_v3 import (
    DEFAULT_TAEH3,
    LEGACY_WRAPPER_KEYS,
    _first_h3_latent,
    _PreviewJob,
    _PreviewWrapperV3,
    _vae_choices,
)

LOGGER = logging.getLogger(__name__)
WRAPPER_KEY = "h3studio_taeh3_preview_v4"
LIVE_MAX_RESOLUTION = 448


def _prepare_preview_latent(torch, x0, latent_shapes, max_resolution: int):
    latent = _first_h3_latent(x0, latent_shapes)
    output_height = int(latent.shape[-2]) * 16
    output_width = int(latent.shape[-1]) * 16
    longest = max(output_height, output_width)
    if longest > int(max_resolution):
        scale = float(max_resolution) / float(longest)
        latent_height = max(1, round(int(latent.shape[-2]) * scale))
        latent_width = max(1, round(int(latent.shape[-1]) * scale))
        latent = torch.nn.functional.interpolate(
            latent,
            size=(latent_height, latent_width),
            mode="bilinear",
            align_corners=False,
        )
    return latent.detach().to(device="cpu", dtype=torch.float32, copy=True)


class _PreviewWrapperV4(_PreviewWrapperV3):
    def _ensure_worker(self) -> None:
        with self._worker_lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._jobs = queue.Queue(maxsize=1)
            self._worker = threading.Thread(
                target=self._worker_main,
                name=f"H3StudioPreviewLatest-{self.node_id or 'preview'}",
                daemon=True,
            )
            self._worker.start()

    def _queue_job(self, job: _PreviewJob) -> None:
        self._ensure_worker()
        try:
            self._jobs.put_nowait(job)
            return
        except queue.Full:
            pass

        # Keep the frame currently decoding, but replace any waiting stale frame
        # with the newest denoise state. The sampler must never wait on preview.
        try:
            self._jobs.get_nowait()
            self._jobs.task_done()
        except queue.Empty:
            pass
        try:
            self._jobs.put_nowait(job)
        except queue.Full:
            LOGGER.debug("[H3 Studio Preview v4] newest frame skipped after queue race")

    def __call__(
        self,
        executor,
        noise,
        latent_image,
        sampler,
        sigmas,
        denoise_mask,
        callback,
        disable_pbar,
        seed,
        latent_shapes,
    ):
        import torch

        self.run_serial += 1
        self.first_frame_reported = False
        run_id = f"{self.node_id}:v4:{self.run_serial}"
        self.active_run_id = run_id
        self._discard_pending()

        total_steps = max(0, len(sigmas) - 1) if sigmas is not None and hasattr(sigmas, "__len__") else 0
        sampling_started = time.perf_counter()

        try:
            self._reset_frontend(total_steps, run_id)
        except Exception as error:
            LOGGER.debug("[H3 Studio Preview v4] reset event skipped: %s", error)

        LOGGER.info(
            "[H3 Studio Preview v4] sampler entered | node=%s | steps=%d | every=%d | latest-only=yes | decoder=cpu | gpu-decoder-residency=0",
            self.node_id,
            total_steps,
            self.every,
        )

        def preview_callback(step, x0, x, callback_total_steps):
            if int(step) % self.every == 0:
                try:
                    final_step = int(step) + 1 >= int(callback_total_steps)
                    effective_max = int(self.max_resolution) if final_step else min(int(self.max_resolution), LIVE_MAX_RESOLUTION)
                    copy_started = time.perf_counter()
                    snapshot = _prepare_preview_latent(torch, x0, latent_shapes, effective_max)
                    elapsed = time.perf_counter() - sampling_started
                    completed = max(1, int(step) + 1)
                    self._queue_job(
                        _PreviewJob(
                            latent=snapshot,
                            latent_shapes=(),
                            step=int(step),
                            total_steps=int(callback_total_steps),
                            run_id=run_id,
                            elapsed_seconds=elapsed,
                            average_step_seconds=elapsed / completed,
                        )
                    )
                    LOGGER.debug(
                        "[H3 Studio Preview v4] latest latent queued | step=%d/%d | max=%d | handoff=%.3fs",
                        int(step) + 1,
                        int(callback_total_steps),
                        effective_max,
                        time.perf_counter() - copy_started,
                    )
                except Exception as error:
                    LOGGER.warning("[H3 Studio Preview v4] preview snapshot skipped: %s", error)
                    self._report_error(error, run_id)

            if callback is not None:
                callback(step, x0, x, callback_total_steps)

        return executor(
            noise,
            latent_image,
            sampler,
            sigmas,
            denoise_mask,
            preview_callback,
            disable_pbar,
            seed,
            latent_shapes=latent_shapes,
        )


class H3StudioTAEH3PreviewV4:
    CATEGORY = "H3 Studio/Preview"
    FUNCTION = "attach"
    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("model",)
    DESCRIPTION = "Latest-frame CPU TAEH3 preview for L4: no decoder VRAM residency and no stale preview backlog."
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "enabled": ("BOOLEAN", {"default": False}),
                "tiny_vae": (_vae_choices(), {"default": DEFAULT_TAEH3}),
                "max_resolution": ("INT", {"default": 512, "min": 256, "max": 1024, "step": 64}),
                "jpeg_quality": ("INT", {"default": 92, "min": 40, "max": 95, "step": 1}),
                "preview_every_n_steps": ("INT", {"default": 1, "min": 1, "max": 20, "step": 1}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    @staticmethod
    def attach(model, enabled, tiny_vae, max_resolution, jpeg_quality, preview_every_n_steps, unique_id=None):
        if not enabled:
            return (model,)

        import comfy.patcher_extension
        import folder_paths

        checkpoint_path = folder_paths.get_full_path("vae_approx", tiny_vae)
        if not checkpoint_path:
            raise FileNotFoundError(
                f"TAEH3 preview file '{tiny_vae}' was not found. Put it in ComfyUI/models/vae_approx/."
            )

        patched = model.clone()
        wrapper_type = comfy.patcher_extension.WrappersMP.OUTER_SAMPLE
        for key in (*LEGACY_WRAPPER_KEYS, WRAPPER_KEY):
            patched.remove_wrappers_with_key(wrapper_type, key)
        patched.add_wrapper_with_key(
            wrapper_type,
            WRAPPER_KEY,
            _PreviewWrapperV4(
                checkpoint_path=checkpoint_path,
                node_id=str(unique_id or ""),
                max_resolution=int(max_resolution),
                jpeg_quality=int(jpeg_quality),
                every=max(1, int(preview_every_n_steps)),
            ),
        )
        LOGGER.info(
            "[H3 Studio Preview v4] attached | node=%s | decoder=%s | max=%d | every=%d | latest-only=yes | cpu-decoder=yes | gpu-decoder-residency=0",
            str(unique_id or ""),
            tiny_vae,
            int(max_resolution),
            max(1, int(preview_every_n_steps)),
        )
        return (patched,)


H3StudioTAEH3Preview = H3StudioTAEH3PreviewV4

__all__ = ["H3StudioTAEH3Preview", "H3StudioTAEH3PreviewV4"]
