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


class FakeStableImage(FakeInferenceImage):
    def __init__(self, pointer: int, pixels: bytes):
        super().__init__(pointer)
        self.pixels = pixels

    def detach(self):
        return self

    def to(self, **_kwargs):
        return self

    def contiguous(self):
        return self

    def numpy(self):
        class Bytes:
            def __init__(self, value):
                self.value = value

            def tobytes(self):
                return self.value

        return Bytes(self.pixels)


class FakeClip:
    def __init__(self):
        self.seen_images = []
        self.generate_calls = 0

    def tokenize(self, instruction, *, images, thinking):
        assert "USER REQUEST:" in instruction
        assert thinking is False
        self.seen_images = images
        return {"tokens": [1]}

    def generate(self, tokens, **kwargs):
        assert kwargs["do_sample"] is False
        self.generate_calls += 1
        return [2]

    def decode(self, generated, *, skip_special_tokens):
        assert skip_special_tokens is True
        return """{"instruction":"Turn the character from @Image1 toward frame-right, add the black rectangular glasses from @Image2, and make him smile visibly.","references":[
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
    analyzed, enhanced, note = analyze_references(
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
    assert "@Image1" in enhanced
    assert "@Image2" in enhanced
    assert "smile visibly" in enhanced
    assert "2 actual reference image" in note
    compiled = PromptCompiler().compile(
        StudioState(
            prompt=enhanced,
            references=analyzed,
        )
    )
    assert compiled.references[0].role == "character"
    assert compiled.references[1].role == "object"
    assert "smile visibly" in compiled.native_prompt


def test_inference_tensor_without_version_counter_is_cacheable() -> None:
    clip = FakeClip()
    references = (
        ReferenceImage("one", "person.jpg", 1),
        ReferenceImage("two", "glasses.png", 2),
    )
    analyzed, _enhanced, _note = analyze_references(
        clip,
        "Show the person in @Image1 with the glasses from @Image2 and make him look to the right",
        references,
        (FakeInferenceImage(303), FakeInferenceImage(404)),
    )
    assert analyzed[0].role == "character"


def test_seed_only_queue_reuses_analysis_across_recreated_runtime_objects(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    monkeypatch.setattr(analyzer_module, "_CACHE_KEY", None)
    monkeypatch.setattr(analyzer_module, "_CACHE_VALUE", None)
    references = (
        ReferenceImage("one", "person.jpg", 1, storage_name="h3studio/person.jpg"),
        ReferenceImage("two", "glasses.png", 2, storage_name="h3studio/glasses.png"),
    )
    prompt = "Show the person in @Image1 with the glasses from @Image2 and make him look to the right"
    first_clip = FakeClip()
    second_clip = FakeClip()

    analyze_references(
        first_clip,
        prompt,
        references,
        (FakeStableImage(501, b"person pixels"), FakeStableImage(502, b"glasses pixels")),
        analyzer_name="qwen3vl_4b_fp8_scaled.safetensors",
    )
    analyzed, enhanced, note = analyze_references(
        second_clip,
        prompt,
        references,
        (FakeStableImage(601, b"person pixels"), FakeStableImage(602, b"glasses pixels")),
        analyzer_name="qwen3vl_4b_fp8_scaled.safetensors",
    )

    assert first_clip.generate_calls == 1
    assert second_clip.generate_calls == 0
    assert analyzed[1].role == "object"
    assert "@Image2" in enhanced
    assert "Cache: HIT" in note


def test_analyzer_rewrite_that_drops_an_image_falls_back_to_original(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    monkeypatch.setattr(analyzer_module, "_CACHE_KEY", None)
    monkeypatch.setattr(analyzer_module, "_CACHE_VALUE", None)
    clip = FakeClip()
    clip.decode = lambda *_args, **_kwargs: """{"instruction":"Only use @Image1.","references":[
      {"ordinal":1,"role":"character","retention":"fully_preserved","description":"Pale clown in a ruffled costume."},
      {"ordinal":2,"role":"object","retention":"attribute_transfer","description":"Rectangular black glasses."}
    ]}"""
    original = "Make @Image1 wear the glasses from @Image2"
    references = (ReferenceImage("one", "one.png", 1), ReferenceImage("two", "two.png", 2))

    _analyzed, enhanced, _note = analyze_references(clip, original, references, (FakeImage(1), FakeImage(2)))

    assert enhanced == original


def test_native_analyzer_detail_keeps_original_image_objects(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    monkeypatch.setattr(analyzer_module, "_CACHE_KEY", None)
    monkeypatch.setattr(analyzer_module, "_CACHE_VALUE", None)
    clip = FakeClip()
    image = FakeImage(909)
    reference = ReferenceImage("one", "one.png", 1)

    analyze_references(clip, "Use @Image1", (reference,), (image,), max_image_edge=0)

    assert clip.seen_images == [image]


def test_prompt_or_uploaded_image_change_invalidates_analysis(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    monkeypatch.setattr(analyzer_module, "_CACHE_KEY", None)
    monkeypatch.setattr(analyzer_module, "_CACHE_VALUE", None)
    clip = FakeClip()
    first = (
        ReferenceImage("one", "person.jpg", 1, storage_name="h3studio/person.jpg"),
        ReferenceImage("two", "glasses.png", 2, storage_name="h3studio/glasses.png"),
    )
    changed = (
        first[0],
        ReferenceImage("two-new", "glasses-2.png", 2, storage_name="h3studio/glasses-2.png"),
    )
    base = "Show @Image1 looking to the right with glasses from @Image2"

    analyze_references(clip, base, first, (FakeImage(1), FakeImage(2)), analyzer_name="qwen")
    analyze_references(clip, f"{base} outdoors", first, (FakeImage(3), FakeImage(4)), analyzer_name="qwen")
    analyze_references(clip, f"{base} outdoors", changed, (FakeImage(5), FakeImage(6)), analyzer_name="qwen")

    assert clip.generate_calls == 3


def test_analyzer_detail_change_invalidates_analysis(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    monkeypatch.setattr(analyzer_module, "_CACHE_KEY", None)
    monkeypatch.setattr(analyzer_module, "_CACHE_VALUE", None)
    clip = FakeClip()
    references = (ReferenceImage("one", "person.jpg", 1, storage_name="h3studio/person.jpg"),)
    images = (FakeStableImage(701, b"person pixels"),)
    prompt = "Use @Image1 as the character"

    analyze_references(clip, prompt, references, images, analyzer_name="qwen", max_image_edge=384)
    analyze_references(clip, prompt, references, images, analyzer_name="qwen", max_image_edge=512)

    assert clip.generate_calls == 2
