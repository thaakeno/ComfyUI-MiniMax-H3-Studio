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


def test_lightning_does_not_auto_enable_fast_disk() -> None:
    source = (ROOT / "h3studio" / "extension_v3.py").read_text(encoding="utf-8")
    assert 'H3STUDIO_DISABLE_AUTO_FAST_DISK", "1"' in source


def test_conditioning_restores_native_no_extra_unload_path() -> None:
    source = (ROOT / "h3studio" / "conditioning_fastpath.py").read_text(encoding="utf-8")
    assert "encode_from_tokens_scheduled" in source
    assert '"HIT", 0.0, "warm-cache"' in source
    assert "release_stage_patcher" not in source
    assert "text_encoder_residency" not in source


def test_preview_decoder_never_allocates_on_cuda() -> None:
    source = (ROOT / "h3studio" / "preview_runtime_v4.py").read_text(encoding="utf-8")
    assert "_PreviewWrapperV3" in source
    assert "gpu-decoder-residency=0" in source
    assert "vae_device" not in source
    assert "decoder_device" not in source


def test_preview_drops_stale_backlog_and_keeps_latest_frame() -> None:
    source = (ROOT / "h3studio" / "preview_runtime_v4.py").read_text(encoding="utf-8")
    assert "queue.Queue(maxsize=1)" in source
    assert "latest-frame" in source
    assert "get_nowait" in source
    assert "put_nowait" in source
    assert "LIVE_MAX_RESOLUTION = 448" in source


def test_v3_preview_preserves_existing_pagination_frontend() -> None:
    source = (ROOT / "web" / "js" / "preview_extension.js").read_text(encoding="utf-8")
    assert "Previous sampling preview" in source
    assert "Next sampling preview" in source
    assert "state.history.push(detail)" in source
