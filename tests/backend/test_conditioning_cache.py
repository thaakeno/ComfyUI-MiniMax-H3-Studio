from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

import h3studio.conditioning_cache as cache


class FakeDynamicPatcher:
    def __init__(self, loaded: int = 4096):
        self._loaded = loaded
        self.calls: list[tuple[object, float]] = []

    def is_dynamic(self):
        return True

    def loaded_size(self):
        return self._loaded

    def partially_unload(self, device_to, memory_to_free=0, force_patch_weights=False):
        assert force_patch_weights is False
        self.calls.append((device_to, memory_to_free))
        freed = self._loaded
        self._loaded = 0
        return freed


class FakeManagedPatcher(FakeDynamicPatcher):
    def is_dynamic(self):
        return False


class FakeClip:
    def __init__(self, name: str):
        self.name = name
        self.patcher = object()
        self.tokenize_calls: list[tuple[str, tuple]] = []
        self.encode_calls = 0

    def tokenize(self, prompt: str, **kwargs):
        marker = tuple(sorted(kwargs))
        self.tokenize_calls.append((prompt, marker))
        return (self.name, prompt, marker)

    def encode_from_tokens_scheduled(self, tokens):
        self.encode_calls += 1
        return {"encoder": self.name, "tokens": tokens, "encode": self.encode_calls}


class FakeVAE:
    def __init__(self):
        self.patcher = object()
        self.encode_calls = 0

    def encode(self, image):
        self.encode_calls += 1
        return ("vae", self.encode_calls, image)


class FakeBundle:
    def __init__(self, *, clip_name="qwen32-a", model_name="fl-a"):
        self.clip_name = clip_name
        self.fl2va_name = model_name
        self.ref2va_name = "ref-a"
        self.video_vae_name = "vae-a"
        self.image_vae_name = None
        self.clip = FakeClip(clip_name)
        self.video_vae = FakeVAE()
        self.image_vae = None
        self.analyzer_clip = None
        self.prompt_writer_clip = None
        self._model = None

    def selected_name(self, route):
        return self.ref2va_name if route == "ref2va" else self.fl2va_name


class FakeImage:
    def __init__(self, pointer: int, version: int = 0, shape=(1, 128, 128, 3)):
        self.pointer = pointer
        self._version = version
        self.shape = shape
        self.dtype = "float32"

    def data_ptr(self):
        return self.pointer


def _install_runtime_stubs(monkeypatch):
    runtime = ModuleType("h3studio.nodes.image_runtime")
    runtime._empty_h3_av_latent = lambda width, height, internal_frames, **kwargs: (
        {"canvas": (width, height), "frames": internal_frames},
        internal_frames,
        internal_frames,
    )
    runtime._resolve_frame_count = lambda frame_preset: int(frame_preset)
    runtime._prompt_warning = lambda prompt: ""
    runtime._reference_resize = lambda image, width, height, reference_size: (image, width, height)
    runtime._resize_image = lambda image, width, height, source_fit: ("resized", image, width, height, source_fit)
    runtime.CANVAS_MULTIPLE = 32
    runtime.REF_IMAGE_SHORT_EDGE = 2048
    monkeypatch.setitem(sys.modules, "h3studio.nodes.image_runtime", runtime)

    node_helpers = ModuleType("node_helpers")
    node_helpers.conditioning_set_values = lambda conditioning, values: (conditioning, values)
    monkeypatch.setitem(sys.modules, "node_helpers", node_helpers)


def _context(prompt: str, width=1024, height=1024, images=(), references=()):
    return SimpleNamespace(
        prompt=prompt,
        width=width,
        height=height,
        images=tuple(images),
        state=SimpleNamespace(references=tuple(references)),
    )


@pytest.fixture(autouse=True)
def _clear_caches():
    cache.clear_conditioning_caches()
    yield
    cache.clear_conditioning_caches()


def test_dynamic_residency_release_frees_device_pages_without_managed_unload():
    dynamic = FakeDynamicPatcher(loaded=8192)
    result = cache.release_dynamic_device_residency(dynamic, "h3")
    assert result.state == "released"
    assert result.freed_bytes == 8192
    assert dynamic.calls == [(None, 1e32)]

    managed = FakeManagedPatcher(loaded=8192)
    result = cache.release_dynamic_device_residency(managed, "vae")
    assert result.state == "managed"
    assert managed.calls == []


def test_image_identity_uses_content_fingerprint_or_tensor_identity():
    reference_a = SimpleNamespace(fingerprint="content-a")
    reference_b = SimpleNamespace(fingerprint="content-b")
    context_a = _context("p", images=(FakeImage(100),), references=(reference_a,))
    context_b = _context("p", images=(FakeImage(100),), references=(reference_b,))
    assert cache.image_cache_key(context_a) != cache.image_cache_key(context_b)

    no_fingerprint = SimpleNamespace(fingerprint=None)
    context_c = _context("p", images=(FakeImage(100),), references=(no_fingerprint,))
    context_d = _context("p", images=(FakeImage(200),), references=(no_fingerprint,))
    context_e = _context("p", images=(FakeImage(100, version=1),), references=(no_fingerprint,))
    key_c = cache.image_cache_key(context_c)
    assert key_c != cache.image_cache_key(context_d)
    assert key_c != cache.image_cache_key(context_e)


def test_t2i_prompt_resolution_encoder_and_model_invalidation_are_independent(monkeypatch):
    _install_runtime_stubs(monkeypatch)
    monkeypatch.setattr(cache, "prepare_text_encoder_workspace", lambda bundle: ())
    monkeypatch.setattr(cache, "release_text_encoder_workspace", lambda clip: cache.ResidencyRelease("text", "managed"))
    monkeypatch.setattr(cache, "_preview_black", lambda width, height: ("black", width, height))

    bundle = FakeBundle()

    first = cache.run_conditioning_pipeline(
        bundle,
        _context("prompt A", 1024, 1024),
        route="fl2va",
        runtime_mode="text_to_image (FL2VA)",
        used_images=(),
        frame_preset="5",
    )
    assert "text_conditioning=MISS" in first.diagnostics
    assert "latent_prepare=MISS" in first.diagnostics
    assert bundle.clip.encode_calls == 1

    identical = cache.run_conditioning_pipeline(
        bundle,
        _context("prompt A", 1024, 1024),
        route="fl2va",
        runtime_mode="text_to_image (FL2VA)",
        used_images=(),
        frame_preset="5",
    )
    assert "text_conditioning=HIT" in identical.diagnostics
    assert "latent_prepare=HIT" in identical.diagnostics
    assert bundle.clip.encode_calls == 1

    prompt_only = cache.run_conditioning_pipeline(
        bundle,
        _context("prompt B", 1024, 1024),
        route="fl2va",
        runtime_mode="text_to_image (FL2VA)",
        used_images=(),
        frame_preset="5",
    )
    assert "text_conditioning=MISS" in prompt_only.diagnostics
    assert "latent_prepare=HIT" in prompt_only.diagnostics
    assert bundle.clip.encode_calls == 2

    resolution_only = cache.run_conditioning_pipeline(
        bundle,
        _context("prompt B", 1408, 1408),
        route="fl2va",
        runtime_mode="text_to_image (FL2VA)",
        used_images=(),
        frame_preset="5",
    )
    assert "text_conditioning=HIT" in resolution_only.diagnostics
    assert "latent_prepare=MISS" in resolution_only.diagnostics
    assert bundle.clip.encode_calls == 2

    new_encoder = FakeBundle(clip_name="qwen32-b", model_name="fl-a")
    encoder_changed = cache.run_conditioning_pipeline(
        new_encoder,
        _context("prompt B", 1408, 1408),
        route="fl2va",
        runtime_mode="text_to_image (FL2VA)",
        used_images=(),
        frame_preset="5",
    )
    assert "text_conditioning=MISS" in encoder_changed.diagnostics
    assert new_encoder.clip.encode_calls == 1

    new_model = FakeBundle(clip_name="qwen32-a", model_name="fl-b")
    model_changed = cache.run_conditioning_pipeline(
        new_model,
        _context("prompt B", 1408, 1408),
        route="fl2va",
        runtime_mode="text_to_image (FL2VA)",
        used_images=(),
        frame_preset="5",
    )
    assert "text_conditioning=MISS" in model_changed.diagnostics
    assert new_model.clip.encode_calls == 1


def test_reference_vae_cache_invalidates_only_changed_reference(monkeypatch):
    _install_runtime_stubs(monkeypatch)
    monkeypatch.setattr(cache, "_reference_target_size", lambda image, reference_size, width, height: (512, 512))

    bundle = FakeBundle()
    image_a = object()
    image_b = object()
    image_b_changed = object()

    a1 = cache._reference_vae_stage(bundle, image_a, ("a", 1), 1024, 1024, "max_identity_2048", image_a)
    b1 = cache._reference_vae_stage(bundle, image_b, ("b", 1), 1024, 1024, "max_identity_2048", image_b)
    assert a1[-1] == "MISS"
    assert b1[-1] == "MISS"
    assert bundle.video_vae.encode_calls == 2

    a2 = cache._reference_vae_stage(bundle, image_a, ("a", 1), 1024, 1024, "max_identity_2048", image_a)
    b2 = cache._reference_vae_stage(bundle, image_b_changed, ("b", 2), 1024, 1024, "max_identity_2048", image_b_changed)
    assert a2[-1] == "HIT"
    assert b2[-1] == "MISS"
    assert bundle.video_vae.encode_calls == 3
