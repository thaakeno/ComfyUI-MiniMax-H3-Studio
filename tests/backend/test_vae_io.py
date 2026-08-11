from __future__ import annotations

from types import SimpleNamespace

from h3studio.vae_io import UPSTREAM_H3_VAE_MERGE, detect_vae_io


def test_detects_native_chunked_h3_vae_contract() -> None:
    vae = SimpleNamespace(first_stage_model=SimpleNamespace(comfy_has_chunked_io=True))
    status = detect_vae_io(vae)
    assert status.chunked is True
    assert status.label == "upstream chunked H3 VAE I/O"
    assert "output buffers" in status.detail


def test_legacy_vae_path_remains_supported_with_actionable_upgrade() -> None:
    status = detect_vae_io(SimpleNamespace(first_stage_model=object()))
    assert status.chunked is False
    assert status.label == "legacy ComfyUI VAE I/O"
    assert "PR #15446" in status.detail
    assert UPSTREAM_H3_VAE_MERGE[:12] in status.detail
