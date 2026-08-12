from __future__ import annotations

import sys
from types import ModuleType

import pytest

from h3studio.nodes.preview import _PreviewWrapper


def test_preview_releases_tiny_decoder_after_sampling(monkeypatch) -> None:
    torch = ModuleType("torch")
    monkeypatch.setitem(sys.modules, "torch", torch)
    wrapper = _PreviewWrapper("taeh3.safetensors", "16", 768, 90, 1)
    wrapper.decoder = object()
    wrapper.decoder_device = "cuda:0"
    wrapper.decoder_dtype = "float16"

    wrapper._release_decoder()

    assert wrapper.decoder is None
    assert wrapper.decoder_device is None
    assert wrapper.decoder_dtype is None


def test_preview_releases_decoder_when_sampler_raises(monkeypatch) -> None:
    torch = ModuleType("torch")
    monkeypatch.setitem(sys.modules, "torch", torch)
    wrapper = _PreviewWrapper("taeh3.safetensors", "16", 768, 90, 1)
    released = []

    monkeypatch.setattr(wrapper, "_load_decoder", lambda _torch: None)
    monkeypatch.setattr(wrapper, "_reset_frontend", lambda *_args: None)
    monkeypatch.setattr(wrapper, "_release_decoder", lambda: released.append(True))

    def explode(*args, **kwargs):
        raise RuntimeError("sampler failed")

    with pytest.raises(RuntimeError, match="sampler failed"):
        wrapper(explode, None, None, None, [1.0, 0.0], None, None, False, 1, [])

    assert released == [True]
