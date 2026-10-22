from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "h3studio" / "nodes" / "decode.py"


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_native_decode_module_is_syntactically_valid_and_keeps_h3_node_name() -> None:
    text = _source()
    ast.parse(text, filename=str(SOURCE))
    assert 'NODE_CLASS_MAPPINGS = {"H3StudioDecode": H3StudioDecode}' in text


def test_auto_mode_preserves_256_64_compatibility_geometry() -> None:
    text = _source()
    assert "_NATIVE_TILE = 256" in text
    assert "_NATIVE_OVERLAP = 64" in text
    assert 'if str(mode).lower() != "manual"' in text


def test_decoder_uses_native_pixels_and_instance_scoped_restore() -> None:
    text = _source()
    assert "model._decode_pixels" in text
    assert "model.tiled_decode = MethodType(adapter, model)" in text
    assert 'delattr(model, "tiled_decode")' in text
    assert "model.tile_size = previous_tile" in text
    assert "model.tile_overlap_min = previous_overlap" in text
    assert "model.tiling = previous_tiling" in text


def test_adapter_accepts_core_frames_selection() -> None:
    text = _source()
    assert "def adapter(instance, z, frames=slice(None)):" in text
    assert "_batched_tiled_decode(instance, z, progress)[:, :, frames]" in text


def test_decoder_has_native_tile_batching_progress_and_oom_backoff() -> None:
    text = _source()
    assert "torch.cat(latent_tiles, dim=0)" in text
    assert "comfy.model_management.is_oom(error)" in text
    assert "progress.note_oom(count)" in text
    assert "PromptServer" in text
    assert '"h3studio.decode_status"' in text
    assert "comfy.utils.ProgressBar" in text


def test_full_packet_path_does_not_clone_decoded_frame_storage() -> None:
    text = _source()
    assert "if kept_frames < natural_frames:" in text
    assert "return flattened.clone()" in text
    assert "return flattened" in text
