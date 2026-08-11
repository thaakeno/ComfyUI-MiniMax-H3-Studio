from __future__ import annotations

from h3studio.image_inputs import image_metadata


class FakePixels:
    shape = (1, 720, 1280, 3)

    def __init__(self, payload: bytes):
        self.payload = payload

    def detach(self):
        return self

    def to(self, **_kwargs):
        return self

    def contiguous(self):
        return self

    def numpy(self):
        payload = self.payload

        class Bytes:
            def tobytes(self):
                return payload

        return Bytes()


def test_image_metadata_is_dimensioned_and_content_stable() -> None:
    first = image_metadata(FakePixels(b"same pixels"))
    recreated = image_metadata(FakePixels(b"same pixels"))
    changed = image_metadata(FakePixels(b"changed pixels"))

    assert first[:2] == (1280, 720)
    assert first[2] == recreated[2]
    assert first[2] != changed[2]
