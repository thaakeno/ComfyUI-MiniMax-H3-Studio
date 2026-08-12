from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_entrypoint_activates_v3_not_v2() -> None:
    source = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "extension_v3" in source
    assert "extension_v2" not in source


def test_v3_registration_reuses_proven_stable_runtime_classes() -> None:
    source = (ROOT / "h3studio" / "extension_v3.py").read_text(encoding="utf-8")
    assert "runtime_node_classes" in source
    assert "H3StudioStableContextSamplingPreset" in source
    assert "H3StudioStableDecode" in source
    assert "runtime_v2" not in source
    assert "recovered_node_classes" not in source


def test_v3_preview_never_allocates_decoder_on_cuda() -> None:
    source = (ROOT / "h3studio" / "preview_runtime_v3.py").read_text(encoding="utf-8")
    assert 'device="cpu"' in source
    assert "gpu-residency=0" in source
    assert "vae_device" not in source
    assert "decoder_device" not in source
    assert "suppressing further accelerated-run previews" not in source


def test_v3_preview_keeps_all_lightx_frames_bufferable() -> None:
    source = (ROOT / "h3studio" / "preview_runtime_v3.py").read_text(encoding="utf-8")
    assert "queue.Queue(maxsize=16)" in source
    assert "int(step) % self.every == 0" in source


def test_v3_preview_preserves_existing_pagination_frontend() -> None:
    source = (ROOT / "web" / "js" / "preview_extension.js").read_text(encoding="utf-8")
    assert "Previous sampling preview" in source
    assert "Next sampling preview" in source
    assert "state.history.push(detail)" in source
