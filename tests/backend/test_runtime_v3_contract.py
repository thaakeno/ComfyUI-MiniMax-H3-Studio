from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_entrypoint_activates_v7_only() -> None:
    source = read("__init__.py")
    assert "extension_v7" in source
    assert "extension_v6" not in source
    assert "extension_v5" not in source
    assert "extension_v3" not in source
    assert "extension_v2" not in source


def test_v7_surface_has_no_startup_model_io() -> None:
    source = read("h3studio/extension_v7.py")
    assert "install_native_max_speed_runtime_v7" in source
    assert "install_conditioning_residency_policy_v7" in source
    assert "install_bundle_route_trace" in source
    assert "H3StudioNativeLoaderV7" in source
    assert "H3StudioNativeSamplingPresetV7" in source
    assert "H3StudioNativeDecodeV7" in source
    assert "H3StudioTAEH3PreviewV5" in source
    assert "start_component_prewarm" not in source
    assert "threading.Thread" not in source
    assert "startup_model_io=False" in source
    assert "startup_prewarm=False" in source
    assert "component_monkeypatch_cache=False" in source
    assert "fast_disk_mutated_by_studio=False" in source


def test_v7_removes_global_component_cache_and_background_prewarm() -> None:
    source = read("h3studio/runtime_v7.py")
    for forbidden in (
        "_CLIP_CACHE",
        "_VAE_CACHE",
        "_UNET_CACHE",
        "_CLIP_LOCK",
        "_VAE_LOCK",
        "_UNET_LOCK",
        "_PREWARM",
        "start_component_prewarm",
        "threading.Thread",
        "loader_module._load_clip =",
        "loader_module._load_vae =",
        "loader_module._load_unet =",
    ):
        assert forbidden not in source
    assert "H3StudioLoader.load(" in source
    assert "startup_model_io=False" in source
    assert "background_threads=0" in source


def test_v7_never_auto_enables_fast_disk() -> None:
    source = read("h3studio/runtime_v7.py")
    assert "args.fast_disk = True" not in source
    assert "args.fast_disk = False" not in source
    assert "fast_disk_mutated_by_studio=False" in source
    assert "--fast-disk is enabled externally" in source
    assert "HOST_PRESSURE_HEADROOM = 8 * GIB" in source
    assert "free_pins(" in source
    assert "evict_active=False" in source


def test_conditioning_delegates_to_native_encode_once() -> None:
    source = read("h3studio/runtime_v7.py")
    assert "native_encode = current" in source
    assert "result = native_encode(bundle, key, build_tokens)" in source
    assert "encode_from_tokens_scheduled" not in source
    assert '"HIT", 0.0, "native-v7; cache=hit; model_management=zero"' in source
    assert "pre_text_diffusion" in source
    assert "torch.cuda.synchronize" not in source
    assert "soft_empty_cache" not in source
    assert "load_models_gpu" not in source


def test_memory_policy_keeps_l4_diffusion_hot_without_force_full_preload() -> None:
    source = read("h3studio/runtime_v7.py")
    assert "KEEP_DIFFUSION_HOT = 20 * GIB" in source
    assert "KEEP_ALL_HOT = 40 * GIB" in source
    assert "hot-diffusion-native-pinned-host" in source
    assert "strict-native-stage-handoff" in source
    assert "resident-high-vram" in source
    assert "attach_sampling_stage_release" in source
    assert 'handoff = "keep-hot"' in source
    assert "sampling_residency=native-comfy-manager" in source
    assert "_remove_force_full_experiment" in source
    assert "force_full_load=True" not in source


def test_high_vram_conditioning_keeps_vae_hot() -> None:
    source = read("h3studio/runtime_v7_conditioning.py")
    assert "policy.keep_all_hot" in source
    assert '"kept-hot-high-vram"' in source
    assert '"v7.conditioning.vae.keep"' in source
    assert '"v7.conditioning.vae.release"' in source


def test_seed_uses_queue_time_reservation_without_prompt_monkeypatch() -> None:
    source = read("web/js/zz_seed_queue_v7.js")
    core = read("web/js/core/state.js")
    studio = read("web/js/studio_extension.js")
    assert "seedWidget.afterQueued" in source
    assert "reserveSeedAfterQueue" in source
    assert "execution_error" in source
    assert "execution_interrupted" in source
    assert "api.queuePrompt =" not in source
    assert "seed_queue_reservations" in core
    assert "reservations - 1" in core
    # Legacy Studio success handling remains compatible but becomes a reservation
    # consumer rather than a second seed authority.
    assert "queueSeedAdvance" in studio
    assert "finishSeedAdvances" in studio
    assert "advanceSeedAfterGeneration" in studio


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


def test_sampling_execution_has_boundary_trace_not_per_step_info_trace() -> None:
    source = read("h3studio/preview_runtime_v5.py")
    assert '"sampling.execute.begin"' in source
    assert '"sampling.execute.end"' in source
    assert '"sampling.execute.error"' in source
    callback = source[source.index("def preview_callback"):source.index("try:\n            result = executor")]
    assert "LOGGER.debug" in callback


def test_structured_trace_reports_memory_io_and_pins_without_syncing() -> None:
    source = read("h3studio/runtime_trace.py")
    assert 'PREFIX = "[H3 Studio Trace]"' in source
    assert 'H3STUDIO_STRUCTURED_TRACE", True' in source
    assert 'H3STUDIO_TRACE_MEMORY", True' in source
    assert 'H3STUDIO_TRACE_MODELS", False' in source
    assert '"pinned_gib"' in source
    assert '"pin_budget_gib"' in source
    assert '"io_read_gib"' in source
    assert '"io_write_gib"' in source
    assert "torch.cuda.synchronize" not in source
    assert "soft_empty_cache" not in source
    assert "load_models_gpu" not in source


def test_loader_trace_reports_resolved_model_sources() -> None:
    source = read("h3studio/runtime_v7.py")
    assert '"v7.model_source"' in source
    assert '"realpath"' in source
    assert '"real_tmpfs"' in source
    assert '"size_gib"' in source


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
    assert "steps=8" in source
    assert "shift_video=6.0" in source
    assert "shift_audio=3.0" in source
    assert "lora_strength=1.0" in source
    assert "LIGHTX_V1_LORA_FILENAME" in source


def test_node_audit_targets_v7() -> None:
    source = read("tools/audit_nodes.py")
    assert "extension_v7.py" in source
    assert "extension_v6.py" not in source
    assert "extension_v5.py" not in source
    assert "extension_v3.py" not in source
