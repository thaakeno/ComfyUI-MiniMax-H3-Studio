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


def test_conditioning_isolates_full_text_encoder_only_on_cache_miss() -> None:
    source = (ROOT / "h3studio" / "conditioning_fastpath.py").read_text(encoding="utf-8")
    assert "force_full_load=True" in source
    assert "release_stage_patcher" in source
    assert "pre_text_diffusion" in source
    assert "text_encoder" in source
    assert '"HIT", 0.0, "warm-cache; diffusion=keep-hot"' in source
    assert "encode_from_tokens_scheduled" in source


def test_sampling_keeps_diffusion_hot_until_next_conditioning_miss() -> None:
    source = (ROOT / "h3studio" / "runtime_stability.py").read_text(encoding="utf-8")
    assert "keep-hot-until-conditioning-miss" in source
    assert "POST_SAMPLE_RELEASE_KEY" in source
    assert "attach_sampling_stage_release" not in source
    assert "Diffusion kept hot" in source


def test_startup_prewarm_reuses_clip_and_vae_components_without_loading_diffusion() -> None:
    extension = (ROOT / "h3studio" / "extension_v3.py").read_text(encoding="utf-8")
    performance = (ROOT / "h3studio" / "nodes" / "performance.py").read_text(encoding="utf-8")
    assert "start_default_bundle_prewarm" in extension
    assert "Startup prewarm policy" in extension
    assert "_CLIP_COMPONENT_CACHE" in performance
    assert "_VAE_COMPONENT_CACHE" in performance
    assert "loader_module._load_clip = cached_clip_loader" in performance
    assert "loader_module._load_vae = cached_vae_loader" in performance
    assert "diffusion=lazy" in performance
    assert "H3STUDIO_DISABLE_STARTUP_PREWARM" in performance


def test_unlocked_seed_is_reserved_at_queue_time_not_waiting_for_execution_success() -> None:
    source = (ROOT / "web" / "js" / "seed_queue_extension.js").read_text(encoding="utf-8")
    assert "api.queuePrompt" in source
    assert "app.queuePrompt has already serialized" in source
    assert "reserveNextSeeds(data)" in source
    assert "advanceSeedAfterGeneration" in source
    assert "queued seed=" in source
    assert "reserved next=" in source
    assert "seed_locked === true" in source


def test_preview_decoder_never_allocates_on_cuda() -> None:
    source = (ROOT / "h3studio" / "preview_runtime_v4.py").read_text(encoding="utf-8")
    assert "_PreviewWrapperV3" in source
    assert "gpu-decoder-residency=0" in source
    assert "vae_device" not in source
    assert "decoder_device" not in source


def test_preview_drops_stale_backlog_and_keeps_latest_frame() -> None:
    source = (ROOT / "h3studio" / "preview_runtime_v4.py").read_text(encoding="utf-8")
    assert "queue.Queue(maxsize=1)" in source
    assert "latest-only" in source
    assert "get_nowait" in source
    assert "put_nowait" in source
    assert "LIVE_MAX_RESOLUTION = 448" in source


def test_v3_preview_preserves_existing_pagination_frontend() -> None:
    source = (ROOT / "web" / "js" / "preview_extension.js").read_text(encoding="utf-8")
    assert "Previous sampling preview" in source
    assert "Next sampling preview" in source
    assert "state.history.push(detail)" in source
