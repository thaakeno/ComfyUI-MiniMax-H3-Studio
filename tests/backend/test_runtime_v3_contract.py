from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_entrypoint_activates_v5_only() -> None:
    source = read("__init__.py")
    assert "extension_v5" in source
    assert "extension_v3" not in source
    assert "extension_v2" not in source


def test_v5_surface_uses_adaptive_max_speed_runtime() -> None:
    source = read("h3studio/extension_v5.py")
    assert "install_max_speed_runtime" in source
    assert "install_conditioning_residency_policy" in source
    assert "install_bundle_route_trace" in source
    assert "H3StudioMaxSpeedLoader" in source
    assert "H3StudioMaxSpeedSamplingPreset" in source
    assert "H3StudioMaxSpeedDecode" in source
    assert "H3StudioTAEH3PreviewV5" in source
    assert "start_component_prewarm" in source
    assert 'emit("extension.ready"' in source
    assert "runtime_stability" not in source
    assert "runtime_diagnostics" not in source
    assert "H3STUDIO_DISABLE_AUTO_FAST_DISK" not in source


def test_low_ram_restores_known_fast_comfy_fast_disk_policy() -> None:
    source = read("h3studio/runtime_v5.py")
    assert "LOW_HOST_RAM = 48 * GIB" in source
    assert "args.fast_disk = True" in source
    assert "H3STUDIO_DISABLE_AUTO_FAST_DISK" in source
    assert "fast-disk enabled for DynamicVRAM" in source


def test_conditioning_has_one_native_load_owner_and_zero_manual_sync_flushes() -> None:
    source = read("h3studio/runtime_v5.py")
    assert source.count("encode_from_tokens_scheduled(tokens)") == 1
    assert '"HIT", 0.0, "max-speed-v5; cache=hit; model_management=zero"' in source
    assert "release_stage_patcher" in source
    assert "torch.cuda.synchronize" not in source
    assert "soft_empty_cache" not in source
    assert "load_models_gpu([patcher]" not in source


def test_memory_policy_keeps_l4_diffusion_hot_but_stages_text_encoder() -> None:
    source = read("h3studio/runtime_v5.py")
    assert "KEEP_DIFFUSION_FOR_VAE = 20 * GIB" in source
    assert "KEEP_ALL_HOT = 40 * GIB" in source
    assert "hot-diffusion-staged-text" in source
    assert "strict-stage-handoff" in source
    assert "resident-high-vram" in source
    assert "attach_sampling_stage_release" in source
    assert 'handoff = "keep-hot"' in source


def test_high_vram_conditioning_keeps_vae_hot() -> None:
    source = read("h3studio/runtime_v5_conditioning.py")
    assert "policy.keep_all_hot" in source
    assert '"kept-hot-high-vram"' in source
    assert '"conditioning.vae_residency.keep"' in source
    assert '"conditioning.vae_residency.release"' in source


def test_sampler_never_force_preloads_diffusion() -> None:
    source = read("h3studio/runtime_v5.py")
    assert "sampling_residency=native-comfy-manager" in source
    assert "_remove_force_full_experiment" in source
    # GPU prewarm is intentionally CLIP/VAE-only. Diffusion/LightX remains lazy
    # so the sampler owns the one real diffusion load.
    worker = source[source.index("def start_component_prewarm"):]
    assert "_cached_unet(" not in worker
    assert 'diffusion="lazy"' in worker


def test_component_construction_has_independent_locks() -> None:
    source = read("h3studio/runtime_v5.py")
    assert "_CLIP_LOCK = threading.RLock()" in source
    assert "_VAE_LOCK = threading.RLock()" in source
    assert "_UNET_LOCK = threading.RLock()" in source
    assert "_CLIP_CACHE" in source
    assert "_VAE_CACHE" in source
    assert "_UNET_CACHE" in source


def test_seed_has_one_authority_and_does_not_wrap_prompt_submission() -> None:
    # Queue-time mutation was a second seed authority beside studio_extension's
    # success-based advancement and could touch live graph state while /prompt
    # was still in flight. v5 removes that extension completely.
    assert not (ROOT / "web" / "js" / "seed_queue_extension.js").exists()
    source = read("web/js/studio_extension.js")
    assert "queueSeedAdvance" in source
    assert "finishSeedAdvances" in source
    assert "execution_success" in source
    assert "advanceSeedAfterGeneration" in source
    assert "api.queuePrompt =" not in source


def test_preview_reuses_stable_model_patcher_identity() -> None:
    source = read("h3studio/preview_runtime_v5.py")
    assert "_PATCHER_CACHE" in source
    assert "_stable_preview_clone" in source
    assert 'return cached[1], "reused"' in source
    assert '"preview.patcher.reuse"' in source
    assert '"preview.patcher.create"' in source
    attach = source[source.index("def attach("):]
    assert "patched, identity = _stable_preview_clone(model, node_id)" in attach
    assert "patched = model.clone()" not in attach


def test_preview_has_zero_decoder_vram_and_zero_gpu_resize_compute() -> None:
    source = read("h3studio/preview_runtime_v5.py")
    assert "gpu_decoder_residency=0" in source
    assert "gpu_preview_compute=0" in source
    assert 'to(device="cpu", dtype=torch.float32, copy=True)' in source
    assert "vae_device" not in source
    assert "queue.Queue(maxsize=1)" not in source  # inherited from v4, not duplicated


def test_sampling_execution_has_boundary_trace_not_per_step_info_trace() -> None:
    source = read("h3studio/preview_runtime_v5.py")
    assert '"sampling.execute.begin"' in source
    assert '"sampling.execute.end"' in source
    assert '"sampling.execute.error"' in source
    callback = source[source.index("def preview_callback"):source.index("try:\n            result = executor")]
    assert "emit(" not in callback.replace('emit(\n                        "preview.snapshot.error"', "")
    assert "LOGGER.debug" in callback


def test_structured_trace_is_default_on_and_never_synchronizes_cuda() -> None:
    source = read("h3studio/runtime_trace.py")
    assert 'PREFIX = "[H3 Studio Trace]"' in source
    assert 'H3STUDIO_STRUCTURED_TRACE", True' in source
    assert 'H3STUDIO_TRACE_MEMORY", True' in source
    assert 'H3STUDIO_TRACE_MODELS", True' in source
    assert "torch.cuda.synchronize" not in source
    assert "soft_empty_cache" not in source
    assert "load_models_gpu" not in source
    assert "event" in source
    assert "seq" in source
    assert "uptime_s" in source


def test_conditioning_pipeline_prints_substage_cache_and_memory_state() -> None:
    source = read("h3studio/conditioning_cache.py")
    for event in (
        "conditioning.pipeline.begin",
        "conditioning.pipeline.end",
        "conditioning.pipeline.error",
        "conditioning.latent.hit",
        "conditioning.latent.miss",
        "conditioning.source_vae.begin",
        "conditioning.source_vae.end",
        "conditioning.reference_vae.begin",
        "conditioning.reference_vae.end",
        "conditioning.vae_handoff",
    ):
        assert event in source


def test_route_trace_exposes_model_switch_and_release_timing() -> None:
    source = read("h3studio/runtime_v5_bundle_trace.py")
    for event in (
        "transformer.route.hit",
        "transformer.route.miss",
        "transformer.route.ready",
        "transformer.route.error",
        "transformer.release.begin",
        "transformer.release.end",
    ):
        assert event in source


def test_lightx_v1_official_recipe_is_unchanged() -> None:
    source = read("h3studio/acceleration.py")
    assert '"lightx_v1_fl2v_8"' in source
    assert 'sampler="euler"' in source
    assert 'steps=8' in source
    assert 'shift_video=6.0' in source
    assert 'shift_audio=3.0' in source
    assert 'lora_strength=1.0' in source
    assert "LIGHTX_V1_LORA_FILENAME" in source


def test_node_audit_targets_v5() -> None:
    source = read("tools/audit_nodes.py")
    assert "extension_v5.py" in source
    assert "extension_v3.py" not in source
