"""Maximum-throughput TAEH3 preview with stable sampler patcher identity.

The critical rule is that the preview node must not manufacture a fresh
ModelPatcher clone on every seed-only rerun. ComfyUI intentionally evicts loaded
clone siblings when a different clone arrives. Reusing one preview clone for the
same upstream sampling model lets the already-hot H3/LightX patcher remain the
same object across executions.

TAEH3 itself stays CPU-only and latest-frame-only. The sampling callback copies
only the tiny first H3 video latent to CPU; decode/JPEG/websocket work remains on
the background worker inherited from v4.
"""

from __future__ import annotations

import logging
import threading
import time
import weakref

from .preview_runtime_v3 import DEFAULT_TAEH3, LEGACY_WRAPPER_KEYS, _first_h3_latent, _PreviewJob, _vae_choices
from .preview_runtime_v4 import _PreviewWrapperV4
from .runtime_trace import emit

LOGGER = logging.getLogger(__name__)
WRAPPER_KEY = "h3studio_taeh3_preview_v5"
_CACHE_LOCK = threading.RLock()
# (id(upstream patcher), node id) -> (weak upstream ref, stable preview clone)
_PATCHER_CACHE: dict[tuple[int, str], tuple[weakref.ReferenceType, object]] = {}


def _stable_preview_clone(model, node_id: str):
    key = (id(model), str(node_id))
    with _CACHE_LOCK:
        cached = _PATCHER_CACHE.get(key)
        if cached is not None and cached[0]() is model:
            emit(
                "preview.patcher.reuse",
                node=node_id,
                upstream_patcher_id=id(model),
                preview_patcher_id=id(cached[1]),
                model_id=id(getattr(model, "model", model)),
            )
            return cached[1], "reused"

        patched = model.clone()

        def cleanup(_ref, cache_key=key):
            with _CACHE_LOCK:
                _PATCHER_CACHE.pop(cache_key, None)
            emit("preview.patcher.evict", node=node_id, upstream_patcher_id=key[0])

        try:
            upstream_ref = weakref.ref(model, cleanup)
        except TypeError:
            # ModelPatcher is weak-referenceable in supported ComfyUI builds;
            # keep a conservative strong identity fallback for unusual forks.
            def upstream_ref():
                return model

        _PATCHER_CACHE[key] = (upstream_ref, patched)
        emit(
            "preview.patcher.create",
            node=node_id,
            upstream_patcher_id=id(model),
            preview_patcher_id=id(patched),
            model_id=id(getattr(model, "model", model)),
        )
        return patched, "new"


class _PreviewWrapperV5(_PreviewWrapperV4):
    """Keep GPU callback work to one tiny latent D2H snapshot."""

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
        run_id = f"{self.node_id}:v5:{self.run_serial}"
        self.active_run_id = run_id
        self._discard_pending()

        total_steps = max(0, len(sigmas) - 1) if sigmas is not None and hasattr(sigmas, "__len__") else 0
        sampling_started = time.perf_counter()
        try:
            self._reset_frontend(total_steps, run_id)
        except Exception as error:
            LOGGER.debug("[H3 Studio Preview v5] reset skipped: %s", error)
            emit("preview.frontend_reset.error", run=run_id, error_type=type(error).__name__, error=str(error))

        emit(
            "sampling.execute.begin",
            memory=True,
            models=True,
            run=run_id,
            node=self.node_id,
            seed=seed,
            steps=total_steps,
            preview_every=self.every,
            preview_decoder="cpu",
            gpu_preview_compute=0,
        )

        def preview_callback(step, x0, x, callback_total_steps):
            if int(step) % self.every == 0:
                try:
                    copy_started = time.perf_counter()
                    # The full first-frame H3 latent is only a few hundred KiB.
                    # Copy it directly instead of running interpolation kernels on
                    # the diffusion GPU. CPU worker owns all preview processing.
                    latent = _first_h3_latent(x0, latent_shapes)
                    snapshot = latent.detach().to(device="cpu", dtype=torch.float32, copy=True)
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
                        "[H3 Studio Preview v5] latent handoff | step=%d/%d | %.4fs | gpu-preview-compute=0",
                        int(step) + 1,
                        int(callback_total_steps),
                        time.perf_counter() - copy_started,
                    )
                except Exception as error:
                    LOGGER.warning("[H3 Studio Preview v5] preview snapshot skipped: %s", error)
                    emit(
                        "preview.snapshot.error",
                        run=run_id,
                        step=int(step) + 1,
                        total_steps=int(callback_total_steps),
                        error_type=type(error).__name__,
                        error=str(error),
                    )
                    self._report_error(error, run_id)

            if callback is not None:
                callback(step, x0, x, callback_total_steps)

        try:
            result = executor(
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
        except Exception as error:
            emit(
                "sampling.execute.error",
                memory=True,
                models=True,
                run=run_id,
                node=self.node_id,
                seed=seed,
                steps=total_steps,
                elapsed_s=time.perf_counter() - sampling_started,
                error_type=type(error).__name__,
                error=str(error),
            )
            raise
        emit(
            "sampling.execute.end",
            memory=True,
            models=True,
            run=run_id,
            node=self.node_id,
            seed=seed,
            steps=total_steps,
            elapsed_s=time.perf_counter() - sampling_started,
            avg_step_s=(time.perf_counter() - sampling_started) / max(1, total_steps),
        )
        return result


class H3StudioTAEH3PreviewV5:
    CATEGORY = "H3 Studio/Preview"
    FUNCTION = "attach"
    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("model",)
    DESCRIPTION = "CPU-only latest TAEH3 preview with a stable sampling patcher so hot H3 weights survive seed reruns."
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
            emit("preview.attach.skip", node=str(unique_id or ""), reason="disabled")
            return (model,)

        import comfy.patcher_extension
        import folder_paths

        checkpoint_path = folder_paths.get_full_path("vae_approx", tiny_vae)
        if not checkpoint_path:
            emit("preview.attach.error", node=str(unique_id or ""), error="tiny_vae_missing", tiny_vae=tiny_vae)
            raise FileNotFoundError(
                f"TAEH3 preview file '{tiny_vae}' was not found. Put it in ComfyUI/models/vae_approx/."
            )

        node_id = str(unique_id or "")
        patched, identity = _stable_preview_clone(model, node_id)
        wrapper_type = comfy.patcher_extension.WrappersMP.OUTER_SAMPLE
        for key in (*LEGACY_WRAPPER_KEYS, "h3studio_taeh3_preview_v4", WRAPPER_KEY):
            patched.remove_wrappers_with_key(wrapper_type, key)
        patched.add_wrapper_with_key(
            wrapper_type,
            WRAPPER_KEY,
            _PreviewWrapperV5(
                checkpoint_path=checkpoint_path,
                node_id=node_id,
                max_resolution=int(max_resolution),
                jpeg_quality=int(jpeg_quality),
                every=max(1, int(preview_every_n_steps)),
            ),
        )
        emit(
            "preview.attach",
            memory=True,
            models=True,
            node=node_id,
            patcher_identity=identity,
            upstream_patcher_id=id(model),
            preview_patcher_id=id(patched),
            model_id=id(getattr(model, "model", model)),
            decoder=tiny_vae,
            max_resolution=int(max_resolution),
            jpeg_quality=int(jpeg_quality),
            every=max(1, int(preview_every_n_steps)),
            decoder_device="cpu",
            gpu_decoder_residency=0,
        )
        return (patched,)


H3StudioTAEH3Preview = H3StudioTAEH3PreviewV5

__all__ = ["H3StudioTAEH3Preview", "H3StudioTAEH3PreviewV5"]
