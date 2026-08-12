from __future__ import annotations

from h3studio.nodes.preview import _PreviewWrapper


def test_eight_step_preview_has_no_hidden_sparse_policy(monkeypatch) -> None:
    wrapper = _PreviewWrapper("taeh3.safetensors", "16", 768, 90, 1)
    queued = []

    monkeypatch.setattr(wrapper, "_decode_pixels", lambda *_args: "pixels")
    monkeypatch.setattr(wrapper, "_queue_preview", lambda job: queued.append(job))

    for step in range(8):
        wrapper._enqueue(None, step, "x0", 8, [], "16:1", 1.0 + step, 1.0)

    assert [job.step for job in queued] == list(range(8))


def test_preview_interval_is_respected_and_final_frame_is_kept(monkeypatch) -> None:
    wrapper = _PreviewWrapper("taeh3.safetensors", "16", 768, 90, 3)
    queued = []

    monkeypatch.setattr(wrapper, "_decode_pixels", lambda *_args: "pixels")
    monkeypatch.setattr(wrapper, "_queue_preview", lambda job: queued.append(job))

    for step in range(8):
        wrapper._enqueue(None, step, "x0", 8, [], "16:1", 1.0 + step, 1.0)

    assert [job.step for job in queued] == [0, 3, 6, 7]
