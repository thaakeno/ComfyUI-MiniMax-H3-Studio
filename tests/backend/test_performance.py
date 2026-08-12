from __future__ import annotations

import inspect

from h3studio import performance
from h3studio.performance import vae_full_stage


class FakePatcher:
    def model_size(self):
        return 3 * 1024**3


class FakeVAE:
    def __init__(self, disable_offload=False):
        self.disable_offload = disable_offload
        self.patcher = FakePatcher()


def test_legacy_vae_stage_restores_existing_offload_policy() -> None:
    vae = FakeVAE(disable_offload=False)

    with vae_full_stage(vae, label="vae_decode") as result:
        assert vae.disable_offload is True
        assert result.mode == "legacy-full-stage"
        assert result.model_bytes == 3 * 1024**3

    assert vae.disable_offload is False
    assert result.load_seconds >= 0


def test_legacy_vae_stage_preserves_preexisting_disable_offload() -> None:
    vae = FakeVAE(disable_offload=True)

    with vae_full_stage(vae):
        assert vae.disable_offload is True

    assert vae.disable_offload is True


def test_performance_module_contains_no_force_full_text_or_sampler_policy() -> None:
    source = inspect.getsource(performance)

    assert "force_full_load" not in source
    assert "PREPARE_SAMPLING" not in source
    assert "text_encoder_residency" not in source
    assert "force_full_residency" not in source
    assert "prewarm_diffusion_model" not in source
