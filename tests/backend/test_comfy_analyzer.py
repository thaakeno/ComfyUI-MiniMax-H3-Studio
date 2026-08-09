from __future__ import annotations

from h3studio.prompting.comfy_analyzer import analyze_references
from h3studio.prompting.compiler import PromptCompiler
from h3studio.references import ReferenceImage
from h3studio.state import StudioState


class FakeImage:
    shape = (1, 640, 640, 3)
    _version = 0

    def __init__(self, pointer: int):
        self.pointer = pointer

    def data_ptr(self) -> int:
        return self.pointer


class FakeInferenceImage(FakeImage):
    @property
    def _version(self):
        raise RuntimeError("Inference tensors do not track version counter.")


class FakeClip:
    def __init__(self):
        self.seen_images = []

    def tokenize(self, instruction, *, images, thinking):
        assert "look to the right" in instruction
        assert thinking is False
        self.seen_images = images
        return {"tokens": [1]}

    def generate(self, tokens, **kwargs):
        assert kwargs["do_sample"] is False
        return [2]

    def decode(self, generated, *, skip_special_tokens):
        assert skip_special_tokens is True
        return """{"references":[
          {"ordinal":1,"role":"character","retention":"fully_preserved","description":"A pale clown with red hair and a white ruffled costume."},
          {"ordinal":2,"role":"object","retention":"attribute_transfer","description":"Thick rectangular black eyeglass frames."}
        ]}"""


def test_native_analyzer_uses_pixels_and_returns_card_descriptions() -> None:
    clip = FakeClip()
    references = (
        ReferenceImage("one", "person.jpg", 1),
        ReferenceImage("two", "glasses.png", 2),
    )
    images = (FakeImage(101), FakeImage(202))
    analyzed, note = analyze_references(
        clip,
        "Show the person in @Image1 with the glasses from @Image2 and make him look to the right",
        references,
        images,
    )
    assert clip.seen_images == list(images)
    assert analyzed[0].role == "character"
    assert analyzed[0].retention == "fully_preserved"
    assert "red hair" in analyzed[0].description
    assert analyzed[1].role == "object"
    assert "black eyeglass frames" in analyzed[1].description
    assert "inspected 2 actual reference" in note
    compiled = PromptCompiler().compile(
        StudioState(
            prompt="Show the person in @Image1 with the glasses from @Image2 and make him look to the right",
            references=analyzed,
        )
    )
    assert compiled.references[0].role == "character"
    assert compiled.references[1].role == "object"


def test_inference_tensor_without_version_counter_is_cacheable() -> None:
    clip = FakeClip()
    references = (
        ReferenceImage("one", "person.jpg", 1),
        ReferenceImage("two", "glasses.png", 2),
    )
    analyzed, _note = analyze_references(
        clip,
        "Show the person in @Image1 with the glasses from @Image2 and make him look to the right",
        references,
        (FakeInferenceImage(303), FakeInferenceImage(404)),
    )
    assert analyzed[0].role == "character"
