from __future__ import annotations

import inspect

from h3studio import preview_runtime_v2


def test_preview_v2_resizes_decoded_rgb_not_latent() -> None:
    captured = {}

    class Functional:
        @staticmethod
        def interpolate(value, *, size, mode):
            captured.update(value=value, size=size, mode=mode)
            return "resized-rgb"

    class NN:
        functional = Functional()

    class Torch:
        nn = NN()

    class Image:
        shape = (1, 3, 736, 1344)

    image = Image()
    result = preview_runtime_v2._resize_rgb(Torch(), image, 512)

    assert result == "resized-rgb"
    assert captured["value"] is image
    assert captured["size"] == (280, 512)
    assert captured["mode"] == "nearest"


def test_preview_v2_has_no_cpu_decoder_or_timing_suppression() -> None:
    source = inspect.getsource(preview_runtime_v2)

    assert "_load_cpu" not in source
    assert "suppressing further accelerated-run previews" not in source
    assert "gpu-tiny-decode=yes" in source
    assert "resize=post-decode" in source


def test_preview_v2_lightx_queue_can_preserve_all_eight_frames() -> None:
    wrapper = preview_runtime_v2._PreviewWrapperV2("taeh3.safetensors", "16", 512, 92, 1)
    wrapper._ensure_worker = lambda: None

    import queue

    wrapper._jobs = queue.Queue(maxsize=16)
    for step in range(8):
        wrapper._queue_preview(
            preview_runtime_v2._PreviewJob(None, step, 8, "run", float(step), 1.0)
        )

    assert wrapper._jobs.qsize() == 8
