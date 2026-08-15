from __future__ import annotations

from types import SimpleNamespace

from h3studio.runtime_contract_fixes import conditioning_contract
from h3studio.runtime_optimization import (
    ATTENTION_PYTORCH,
    ATTENTION_SAGE,
    RuntimeCapabilities,
    RuntimeWorkload,
    resolve_runtime,
)
from h3studio.runtime_policy_fixes import _truthful_runtime_resolver


def _context(mode: str, route: str, images=()):
    return SimpleNamespace(
        compile_result=SimpleNamespace(resolved_mode=mode),
        route=SimpleNamespace(selected=route),
        images=tuple(images),
    )


def _caps(*, ck: bool, sage: bool = True, low: bool = True):
    return RuntimeCapabilities(
        os_name="Linux",
        gpu_name="NVIDIA L4",
        total_vram_gb=22.0,
        free_vram_gb=4.0,
        compute_capability="sm89",
        ck_attention=ck,
        sage_mem_eff=sage,
        low_vram_attention=low,
    )


def _work():
    return RuntimeWorkload(
        route="fl2va",
        mode="text_to_image",
        reference_count=0,
        frames=5,
        width=2176,
        height=928,
        megapixels=2.02,
        sequence_length=4908,
        sequence_breakdown="total=4908",
    )


def test_explicit_t2i_never_pixel_conditions_connected_images():
    contract = conditioning_contract(_context("text_to_image", "fl2va", ("image-1", "image-2")))
    assert contract.runtime_mode == "text_to_image (FL2VA)"
    assert contract.used_images == ()
    assert "text-only" in contract.pixel_conditioning


def test_fl2va_i2i_uses_only_image_one_as_exact_source_anchor():
    contract = conditioning_contract(_context("image_to_image", "fl2va", ("image-1", "image-2")))
    assert contract.runtime_mode == "image_to_image (FL2VA)"
    assert contract.used_images == ("image-1",)
    assert "frame-0" in contract.pixel_conditioning


def test_ref2va_uses_the_complete_ordered_reference_set():
    contract = conditioning_contract(_context("reference_edit", "ref2va", ("image-1", "image-2")))
    assert contract.runtime_mode == "reference_edit (REF2VA)"
    assert contract.used_images == ("image-1", "image-2")


def test_fast_without_ck_does_not_silently_become_sage_memory_mode():
    resolver = _truthful_runtime_resolver(resolve_runtime)
    decision = resolver("fast", _caps(ck=False), _work())
    assert decision.attention_backend == ATTENTION_PYTORCH
    assert decision.head_chunks == 1
    assert any("PyTorch" in note for note in decision.fallbacks)


def test_low_and_extreme_remain_explicit_memory_modes():
    resolver = _truthful_runtime_resolver(resolve_runtime)
    low = resolver("low_vram", _caps(ck=False), _work())
    extreme = resolver("extreme_low_vram", _caps(ck=False), _work())
    assert low.attention_backend == ATTENTION_SAGE
    assert low.head_chunks == 2
    assert extreme.attention_backend == ATTENTION_SAGE
    assert extreme.head_chunks >= 4
