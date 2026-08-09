from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from h3studio.image_inputs import collect_images


def test_director_is_valid_with_no_images() -> None:
    images, filenames, storage_names = collect_images({})
    assert images == ()
    assert filenames == ()
    assert storage_names == ()


def test_director_loads_integrated_upload_through_comfy_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class FakeLoadImage:
        def load_image(self, storage_name):
            calls.append(storage_name)
            return "IMAGE_TENSOR", "MASK_TENSOR"

    monkeypatch.setitem(sys.modules, "nodes", SimpleNamespace(LoadImage=FakeLoadImage))
    images, filenames, storage_names = collect_images(
        {"media_filename_1": "h3studio/portrait.png", "media_type_1": "image"}
    )
    assert calls == ["h3studio/portrait.png"]
    assert images == ("IMAGE_TENSOR",)
    assert filenames == ("portrait.png",)
    assert storage_names == ("h3studio/portrait.png",)


def test_linked_tensor_does_not_reload_filename(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnexpectedLoad:
        def load_image(self, _storage_name):
            raise AssertionError("linked tensors must not be loaded from storage")

    monkeypatch.setitem(sys.modules, "nodes", SimpleNamespace(LoadImage=UnexpectedLoad))
    images, filenames, storage_names = collect_images(
        {"media_1": "LINKED_TENSOR", "media_filename_1": "source.png", "media_type_1": "image"}
    )
    assert images == ("LINKED_TENSOR",)
    assert filenames == ("source.png",)
    assert storage_names == (None,)


def test_unsafe_storage_path_fails_before_loading() -> None:
    with pytest.raises(ValueError, match="invalid ComfyUI input filename"):
        collect_images({"media_filename_1": "../secret.png", "media_type_1": "image"})
