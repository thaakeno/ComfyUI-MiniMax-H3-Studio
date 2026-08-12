from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_entrypoint_activates_v6_only() -> None:
    source = read("__init__.py")
    assert "extension_v6" in source
    assert "extension_v5" not in source
    assert "extension_v3" not in source
    assert "extension_v2" not in source


def test_v6_surface_has_no_startup_model_io() -> None:
    source = read("h3studio/extension_v6.py")
    assert "install_native_max_speed_runtime" in source
    assert "install_conditioning_residency_policy" in source
    assert "install_bundle_route_trace" in source
    assert "H3StudioNativeLoader" in source
    assert "H3StudioNativeSamplingPreset" in source
    assert "H3StudioNativeDecode" in source
    assert "H3StudioTAEH3PreviewV5" in source
    assert "start_component_prewarm" not in source
    assert "threading.Thread" not in source
    assert "startup_model_io=False" in source
    assert "startup_prewarm=False" in source
    assert "component_monkeypatch_cache=False" in source


def test_v6_removes_global_component_cache_and_background_prewarm() -> None:
    source = read("h3studio/runtime_v6.py")
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


def test_low_ram_keeps_known_fast_comfy_fast_disk_policy() -> None:
    source = read("h3studio/runtime_v6.py")
    assert "LOW_HOST_RAM = 48 * GIB" in source
    assert "args.fast_disk = True" in source
    assert "H3STUDIO_DISABLE_AUTO_FAST_DISK" in source
    assert "startup_prewarm=False" in source


def test_conditioning_delegates_to_native_encode_once() -> None:
    source = read("h3studio/runtime_v6.py")
    assert "native_encode = current" in source
    assert "result = native_encode(bundle, key, build_tokens)" in source
    assert "encode_from_tokens_scheduled" not in source
    assert '"HIT", 0.0, "native-v6; cache=hit; model_management=zero"' in source
    assert "pre_text_diffusion" in source
    assert "torch.cuda.synchronize" not in source
    assert "soft_empty_cache" not in source
    assert "load_models_gpu" not in source


def test_memory_policy_keeps_l4_diffusion_hot_without_force_full_preload() -> None:
    source = read("h3studio/runtime_v6.py")
    assert "KEEP_DIFFUSION_HOT = 20 * GIB" in source
    assert "KEEP_ALL_HOT = 40 * GIB" in source
    assert "hot-diffusion-native-stages" in source
    assert "strict-native-stage-handoff" in source
    assert "resident-high-vram" in source
    assert "attach_sampling_stage_release" in source
    assert 'handoff = "keep-hot"' in source
    assert "sampling_residency=native-comfy-manager" in source
    assert "_remove_force_full_experiment" in source
    assert "force_full_load=True" not in source


def test_high_vram_conditioning_keeps_vae_hot() -> None:
    source = read("h3studio/runtime_v6_conditioning.py")
    assert "policy.keep_all_hot" in source
    assert '"kept-hot-high-vram"' in source
    assert '"v6.conditioning.vae.keep"' in source
    assert '"v6.conditioning.vae.release"' in source


def test_seed_has_one_authority_and_does_not_wrap_prompt_submission() -> None:
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


def test_sampling_execution_has_boundary_trace_not_per_step_info_trace() -> None:
    source = read("h3studio/preview_runtime_v5.py")
    assert '"sampling.execute.begin"' in source
    assert '"sampling.execute.end"' in source
    assert '"sampling.execute.error"' in source
    callback = source[source.index("def preview_callback"):source.index("try:\n            result = executor")]
    assert "LOGGER.debug" in callback


def test_structured_trace_is_compact_by_default() -> None:
    source = read("h3studio/runtime_trace.py")
    assert 'PREFIX = "[H3 Studio Trace]"' in source
    assert 'H3STUDIO_STRUCTURED_TRACE", True' in source
    assert 'H3STUDIO_TRACE_MEMORY", True' in source
    assert 'H3STUDIO_TRACE_MODELS", False' in source
    assert "torch.cuda.synchronize" not in source
    assert "soft_empty_cache" not in source
    assert "load_models_gpu" not in source


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


def test_node_audit_targets_v6() -> None:
    source = read("tools/audit_nodes.py")
    assert "extension_v6.py" in source
    assert "extension_v5.py" not in source
    assert "extension_v3.py" not in source
