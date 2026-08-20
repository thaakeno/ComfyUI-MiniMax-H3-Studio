from __future__ import annotations

import threading
from types import SimpleNamespace

from h3studio import single_frame_vae_500k as support


COMFY_500K = "minimax_h3_single_frame_vae_500k_comfy.safetensors"
ORIGINAL_DECODER = "minimax_h3_single_frame_decoder_500k.safetensors"
LEGACY_T1 = "minimax_h3_t1_image_vae_step1597.safetensors"
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"


def test_filename_detection_keeps_legacy_and_prefers_comfy_500k() -> None:
    assert support.is_single_frame_image_vae(COMFY_500K)
    assert support.is_single_frame_500k(COMFY_500K)
    assert support.is_single_frame_image_vae(LEGACY_T1)
    assert not support.is_single_frame_image_vae(VIDEO_VAE)
    assert support.image_vae_preference(COMFY_500K) < support.image_vae_preference(LEGACY_T1)


def test_original_decoder_only_filename_is_not_treated_as_ready_comfy_vae() -> None:
    assert support.is_single_frame_500k(ORIGINAL_DECODER)
    assert support.is_obvious_decoder_only_500k(ORIGINAL_DECODER)
    assert not support.is_obvious_decoder_only_500k("minimax_h3_single_frame_decoder_500k_comfy.safetensors")


def test_500k_marks_vae_with_still_image_auto_profile() -> None:
    first_stage = SimpleNamespace(vae_ratio=16)
    vae = SimpleNamespace(first_stage_model=first_stage)

    assert support.mark_loaded_vae(vae, COMFY_500K) is vae
    assert vae._h3studio_image_vae_name == COMFY_500K
    assert first_stage._h3studio_image_vae_name == COMFY_500K
    assert first_stage._h3studio_auto_tile_size == 512
    assert first_stage._h3studio_auto_tile_overlap == 64


def test_legacy_image_vae_keeps_native_auto_profile() -> None:
    vae = SimpleNamespace(first_stage_model=SimpleNamespace())
    support.mark_loaded_vae(vae, LEGACY_T1)
    assert vae.first_stage_model._h3studio_auto_tile_size == 256
    assert vae.first_stage_model._h3studio_auto_tile_overlap == 64


def test_loader_patch_lists_comfy_500k_and_hides_obvious_decoder_only() -> None:
    class FakeLoaderNode:
        @classmethod
        def INPUT_TYPES(cls):
            return {
                "required": {
                    "image_vae": (["Disabled"], {"default": "Disabled", "tooltip": "old"}),
                }
            }

    class FakeBundle:
        def __init__(self, name: str):
            self.image_vae_name = name
            self.image_vae = None
            self._lock = threading.RLock()

    loaded = []

    def load_vae(name: str):
        loaded.append(name)
        return SimpleNamespace(first_stage_model=SimpleNamespace(vae_ratio=16))

    fake = SimpleNamespace(
        _filenames=lambda category: [VIDEO_VAE, ORIGINAL_DECODER, LEGACY_T1, COMFY_500K],
        _load_vae=load_vae,
        DISABLED_IMAGE_VAE="Disabled",
        H3StudioLoader=FakeLoaderNode,
        H3StudioBundle=FakeBundle,
    )

    support._install_loader_support(fake)

    choices = fake.image_vae_choices()
    assert choices == ["Disabled", COMFY_500K, LEGACY_T1]
    assert "500K" in FakeLoaderNode.INPUT_TYPES()["required"]["image_vae"][1]["tooltip"]

    bundle = FakeBundle(COMFY_500K)
    image_vae = bundle.image_vae_for_decode()
    assert loaded == [COMFY_500K]
    assert image_vae.first_stage_model._h3studio_auto_tile_size == 512


def test_decode_patch_uses_500k_auto_profile_and_retries_oom_at_native_geometry() -> None:
    class FakeOOM(RuntimeError):
        pass

    calls = []
    cache_clears = []

    class FakeDecodeNode:
        DESCRIPTION = "old"

        @classmethod
        def INPUT_TYPES(cls):
            return {
                "optional": {
                    "tiling_mode": (["Auto", "Manual"], {"default": "Auto", "tooltip": "old"}),
                }
            }

        def decode(
            self,
            samples,
            vae,
            tiling_mode="Auto",
            tile_size=256,
            tile_overlap=64,
            tile_batch="Auto",
            unique_id=None,
        ):
            calls.append((tiling_mode, tile_size, tile_overlap))
            if tiling_mode == "Auto":
                raise FakeOOM("out of memory")
            return "ok", 1, "retried", 0

    def original_resolve(model, mode, tile_size, overlap):
        if str(mode).lower() == "manual":
            return tile_size, overlap
        return 256, 64

    fake = SimpleNamespace(
        _resolve_spatial_settings=original_resolve,
        _aligned=lambda value, alignment, minimum: max(minimum, round(value / alignment) * alignment),
        H3StudioDecode=FakeDecodeNode,
        comfy=SimpleNamespace(
            model_management=SimpleNamespace(
                is_oom=lambda error: isinstance(error, FakeOOM),
                soft_empty_cache=lambda: cache_clears.append(True),
            )
        ),
    )

    support._install_decode_support(fake)

    tagged_model = SimpleNamespace(
        vae_ratio=16,
        _h3studio_image_vae_name=COMFY_500K,
        _h3studio_auto_tile_size=512,
        _h3studio_auto_tile_overlap=64,
    )
    assert fake._resolve_spatial_settings(tagged_model, "Auto", 256, 64) == (512, 64)
    assert fake._resolve_spatial_settings(tagged_model, "Manual", 384, 80) == (384, 80)

    vae = SimpleNamespace(first_stage_model=tagged_model)
    result = FakeDecodeNode().decode({}, vae)
    assert result == ("ok", 1, "retried", 0)
    assert calls == [("Auto", 256, 64), ("Manual", 256, 64)]
    assert cache_clears == [True]
    assert "500K" in FakeDecodeNode.DESCRIPTION
