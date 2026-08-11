from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

import h3studio.conditioning_cache as cache


class FakeClip:
    def __init__(self, name="clip-a"):
        self.name = name
        self.patcher = object()
        self.encode_calls = 0

    def tokenize(self, prompt, **kwargs):
        return self.name, prompt, tuple(sorted(kwargs))

    def encode_from_tokens_scheduled(self, tokens):
        self.encode_calls += 1
        return {"tokens": tokens, "call": self.encode_calls}


class FakeVAE:
    def __init__(self):
        self.patcher = object()
        self.encode_calls = 0

    def encode(self, image):
        self.encode_calls += 1
        return "vae", self.encode_calls, image


class FakeBundle:
    def __init__(self, clip_name="clip-a", model_name="fl-a"):
        self.clip_name = clip_name
        self.fl2va_name = model_name
        self.ref2va_name = "ref-a"
        self.video_vae_name = "vae-a"
        self.clip = FakeClip(clip_name)
        self.video_vae = FakeVAE()

    def selected_name(self, route):
        return self.ref2va_name if route == "ref2va" else self.fl2va_name


class FakeImage:
    def __init__(self, pointer, version=0, shape=(1, 128, 128, 3)):
        self.pointer = pointer
        self._version = version
        self.shape = shape
        self.dtype = "float32"

    def data_ptr(self):
        return self.pointer


def _runtime_stubs(monkeypatch):
    runtime = ModuleType("h3studio.nodes.image_runtime")
    runtime._empty_h3_av_latent = lambda width, height, frames, **kwargs: (
        {"canvas": (width, height), "frames": frames}, frames, frames
    )
    runtime._resolve_frame_count = int
    runtime._prompt_warning = lambda prompt: ""
    runtime._reference_resize = lambda image, width, height, reference_size: (image, width, height)
    runtime._resize_image = lambda image, width, height, fit: ("resized", image, width, height, fit)
    runtime.CANVAS_MULTIPLE = 32
    runtime.REF_IMAGE_SHORT_EDGE = 2048
    monkeypatch.setitem(sys.modules, "h3studio.nodes.image_runtime", runtime)
    helpers = ModuleType("node_helpers")
    helpers.conditioning_set_values = lambda conditioning, values: (conditioning, values)
    monkeypatch.setitem(sys.modules, "node_helpers", helpers)


def _context(prompt, width=1024, height=1024, images=(), references=()):
    return SimpleNamespace(
        prompt=prompt,
        width=width,
        height=height,
        images=tuple(images),
        state=SimpleNamespace(references=tuple(references)),
    )


@pytest.fixture(autouse=True)
def _clear():
    cache.clear_conditioning_caches()
    yield
    cache.clear_conditioning_caches()


def test_prompt_and_latent_invalidation_are_independent(monkeypatch) -> None:
    _runtime_stubs(monkeypatch)
    monkeypatch.setattr(cache, "_preview_black", lambda width, height: ("black", width, height))
    bundle = FakeBundle()

    first = cache.run_conditioning_pipeline(
        bundle, _context("A"), route="fl2va", runtime_mode="text_to_image (FL2VA)", used_images=(), frame_preset="5"
    )
    assert "text_conditioning=MISS" in first.diagnostics
    assert "latent_prepare=MISS" in first.diagnostics

    prompt_only = cache.run_conditioning_pipeline(
        bundle, _context("B"), route="fl2va", runtime_mode="text_to_image (FL2VA)", used_images=(), frame_preset="5"
    )
    assert "text_conditioning=MISS" in prompt_only.diagnostics
    assert "latent_prepare=HIT" in prompt_only.diagnostics

    resolution_only = cache.run_conditioning_pipeline(
        bundle,
        _context("B", 1408, 1408),
        route="fl2va",
        runtime_mode="text_to_image (FL2VA)",
        used_images=(),
        frame_preset="5",
    )
    assert "text_conditioning=HIT" in resolution_only.diagnostics
    assert "latent_prepare=MISS" in resolution_only.diagnostics
    assert bundle.clip.encode_calls == 2


def test_prompt_cache_invalidates_for_encoder_and_model(monkeypatch) -> None:
    _runtime_stubs(monkeypatch)
    monkeypatch.setattr(cache, "_preview_black", lambda width, height: None)
    context = _context("same")
    for bundle in (FakeBundle(), FakeBundle("clip-b"), FakeBundle("clip-a", "fl-b")):
        result = cache.run_conditioning_pipeline(
            bundle, context, route="fl2va", runtime_mode="text_to_image (FL2VA)", used_images=(), frame_preset="5"
        )
        assert "text_conditioning=MISS" in result.diagnostics


def test_reference_vae_cache_invalidates_only_changed_image(monkeypatch) -> None:
    _runtime_stubs(monkeypatch)
    monkeypatch.setattr(cache, "_reference_target_size", lambda *args: (512, 512))
    bundle = FakeBundle()
    image_a, image_b, changed_b = object(), object(), object()
    assert cache._reference_vae_stage(bundle, image_a, ("a", 1), 1024, 1024, "max_identity_2048", image_a)[-1] == "MISS"
    assert cache._reference_vae_stage(bundle, image_b, ("b", 1), 1024, 1024, "max_identity_2048", image_b)[-1] == "MISS"
    assert cache._reference_vae_stage(bundle, image_a, ("a", 1), 1024, 1024, "max_identity_2048", image_a)[-1] == "HIT"
    assert cache._reference_vae_stage(bundle, changed_b, ("b", 2), 1024, 1024, "max_identity_2048", changed_b)[-1] == "MISS"
    assert bundle.video_vae.encode_calls == 3


def test_image_key_uses_fingerprint_or_live_tensor_identity() -> None:
    image = FakeImage(100)
    assert cache.image_cache_key(_context("p", images=(image,), references=(SimpleNamespace(fingerprint="a"),))) != cache.image_cache_key(
        _context("p", images=(image,), references=(SimpleNamespace(fingerprint="b"),))
    )
    assert cache.image_cache_key(_context("p", images=(FakeImage(100),))) != cache.image_cache_key(
        _context("p", images=(FakeImage(100, version=1),))
    )


def test_production_cache_has_no_manual_dynamic_vram_eviction() -> None:
    assert not hasattr(cache, "release_dynamic_device_residency")
    assert "partially_unload" not in __import__("inspect").getsource(cache)
