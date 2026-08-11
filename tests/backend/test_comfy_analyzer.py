from __future__ import annotations

import json

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
        self.instruction = ""

    def tokenize(self, instruction, *, images, thinking):
        assert "USER REQUEST:" in instruction
        assert thinking is False
        self.instruction = instruction
        self.seen_images = images
        return {"tokens": [1]}

    def generate(self, tokens, **kwargs):
        assert kwargs["do_sample"] is False
        self.generate_calls += 1
        return [2]

    def decode(self, generated, *, skip_special_tokens):
        assert skip_special_tokens is True
        return """{"instruction":"Turn the character from @Image1 toward frame-right, add the black rectangular glasses from @Image2, and make him smile visibly.","references":[
          {"ordinal":1,"role":"character","retention":"fully_preserved","description":"A pale-faced clown character fills most of a centered portrait frame, with bright red swept-back hair, dark painted eye details, and a neutral forward gaze. The figure wears a layered white ruffled costume with red accents. Soft frontal lighting separates the character from a muted indoor background, while the close camera angle keeps the face and upper clothing clearly visible."},
          {"ordinal":2,"role":"object","retention":"attribute_transfer","description":"A pair of thick rectangular black eyeglass frames appears alone against a plain light background. The front-facing product view clearly shows the wide rims, bridge, folded dark temples, glossy plastic material, and symmetrical proportions. Even diffuse lighting produces small edge highlights without strong shadows, and no person, branding, typography, or additional accessory is visible."}
        ]}"""


class FakeWriter:
    def __init__(self):
        self.generate_calls = 0
        self.instruction = ""

    def tokenize(self, instruction, *, images, thinking):
        assert "senior image prompt director" in instruction
        assert images == []
        assert thinking is False
        self.instruction = instruction
        return {"tokens": [1]}

    def generate(self, tokens, **kwargs):
        assert kwargs["do_sample"] is True
        self.generate_calls += 1
        return [2]

    def decode(self, generated, *, skip_special_tokens):
        words = [
            "Create",
            "one",
            "coherent",
            "portrait",
            "of",
            "@Image1",
            "outside",
            "with",
            "clear",
            "identity",
            "deliberate",
            "framing",
            "natural",
            "lighting",
            "credible",
            "materials",
            "and",
            "a",
            "readable",
            "silhouette",
        ]
        instruction = " ".join(words + ["visually"] * 235)
        return json.dumps({"instruction": instruction})


class RetryClip(FakeClip):
    def decode(self, generated, *, skip_special_tokens):
        if self.generate_calls == 1:
            return '{"references":['
        return super().decode(generated, skip_special_tokens=skip_special_tokens)


class BrokenClip(FakeClip):
    def decode(self, generated, *, skip_special_tokens):
        return "not structured output"


class TruncatedClip(FakeClip):
    def decode(self, generated, *, skip_special_tokens):
        return (
            '{"references":[{"ordinal":1,"role":"character","description":"A pale clown fills a centered portrait frame with bright red hair, dark eye makeup, and a layered white costume. The figure faces forward beneath soft frontal lighting, while a quiet indoor background stays out of focus. The close camera position emphasizes the visible face, ruffles, red accents, and symmetrical upper-body composition without showing the lower body."},'
            '{"ordinal":2,"role":"object","description":"Thick rectangular black glasses appear alone in a front-facing product view against a plain light background. Wide glossy rims surround clear lenses, joined by a short bridge, with dark temples folded behind the frame. Soft even lighting creates restrained highlights and weak shadows; no person, logo, printed text, case, or other accessory is visible'
        )


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
    assert "red swept-back hair" in analyzed[0].description
    assert len(analyzed[0].description.split()) >= 35
    assert analyzed[1].role == "object"
    assert "black eyeglass frames" in analyzed[1].description
    assert "@Image1" in enhanced
    assert "@Image2" in enhanced
    assert "look to the right" in enhanced
    assert "2 actual reference image" in note
    compiled = PromptCompiler().compile(
        StudioState(
            prompt=enhanced,
            references=analyzed,
        )
    )
    assert compiled.references[0].role == "character"
    assert compiled.references[1].role == "object"
    assert "look to the right" in compiled.native_prompt


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


def test_truncated_json_prefix_is_repaired_without_another_vision_pass() -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    analyzer_module._ANALYSIS_CACHE.clear()
    clip = TruncatedClip()
    references = (ReferenceImage("one", "one.png", 1), ReferenceImage("two", "two.png", 2))
    analyzed, _enhanced, _note = analyze_references(
        clip, "Use @Image1 and @Image2", references, (FakeImage(1), FakeImage(2))
    )

    assert clip.generate_calls == 1
    assert analyzed[1].description.startswith("Thick rectangular black glasses")
    assert len(analyzed[1].description.split()) >= 35


def test_malformed_analysis_retries_once_then_uses_valid_records() -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    analyzer_module._ANALYSIS_CACHE.clear()
    clip = RetryClip()
    references = (ReferenceImage("one", "one.png", 1), ReferenceImage("two", "two.png", 2))
    analyzed, _enhanced, _note = analyze_references(
        clip, "Use @Image1 and @Image2", references, (FakeImage(11), FakeImage(12))
    )

    assert clip.generate_calls == 2
    assert "red swept-back hair" in analyzed[0].description


def test_repeated_malformed_analysis_fails_soft_and_preserves_existing_cards() -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    analyzer_module._ANALYSIS_CACHE.clear()
    clip = BrokenClip()
    reference = ReferenceImage(
        "one",
        "one.png",
        1,
        role="style",
        description="Existing factual description",
        role_auto=False,
        description_auto=False,
    )
    analyzed, enhanced, note = analyze_references(clip, "Restyle @Image1", (reference,), (FakeImage(21),))

    assert clip.generate_calls == 2
    assert analyzed[0].role == "style"
    assert analyzed[0].description == "Existing factual description"
    assert enhanced == "Restyle @Image1"
    assert "malformed after repair and retry" in note


def test_seed_only_queue_reuses_analysis_across_recreated_runtime_objects(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    analyzer_module._ANALYSIS_CACHE.clear()
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

    analyzer_module._ANALYSIS_CACHE.clear()
    clip = FakeClip()
    clip.decode = lambda *_args, **_kwargs: (
        """{"instruction":"Only use @Image1.","references":[
      {"ordinal":1,"role":"character","retention":"fully_preserved","description":"Pale clown in a ruffled costume."},
      {"ordinal":2,"role":"object","retention":"attribute_transfer","description":"Rectangular black glasses."}
    ]}"""
    )
    original = "Make @Image1 wear the glasses from @Image2"
    references = (ReferenceImage("one", "one.png", 1), ReferenceImage("two", "two.png", 2))

    _analyzed, enhanced, _note = analyze_references(clip, original, references, (FakeImage(1), FakeImage(2)))

    assert enhanced == original


def test_native_analyzer_detail_keeps_original_image_objects(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    analyzer_module._ANALYSIS_CACHE.clear()
    clip = FakeClip()
    image = FakeImage(909)
    reference = ReferenceImage("one", "one.png", 1)

    analyze_references(clip, "Use @Image1", (reference,), (image,), max_image_edge=0)

    assert clip.seen_images == [image]


def test_factual_analyzer_instruction_is_independent_of_named_style_request(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    analyzer_module._ANALYSIS_CACHE.clear()
    clip = FakeClip()
    reference = ReferenceImage("one", "person.png", 1)

    analyze_references(clip, "Turn @Image1 into JoJo anime style", (reference,), (FakeImage(111),))

    assert "Turn @Image1 into JoJo anime style" not in clip.instruction
    assert "Describe only immutable visible source facts" in clip.instruction


def test_prompt_change_reuses_facts_but_uploaded_image_change_invalidates_analysis(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    analyzer_module._ANALYSIS_CACHE.clear()
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

    analyze_references(
        clip,
        base,
        first,
        (FakeStableImage(1, b"person"), FakeStableImage(2, b"glasses")),
        analyzer_name="qwen",
    )
    analyze_references(
        clip,
        f"{base} outdoors",
        first,
        (FakeStableImage(3, b"person"), FakeStableImage(4, b"glasses")),
        analyzer_name="qwen",
    )
    analyze_references(
        clip,
        f"{base} outdoors",
        changed,
        (FakeStableImage(5, b"person"), FakeStableImage(6, b"new glasses")),
        analyzer_name="qwen",
    )

    assert clip.generate_calls == 2
    assert len(clip.seen_images) == 1


def test_analyzer_detail_change_invalidates_analysis(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    analyzer_module._ANALYSIS_CACHE.clear()
    clip = FakeClip()
    references = (ReferenceImage("one", "person.jpg", 1, storage_name="h3studio/person.jpg"),)
    images = (FakeStableImage(701, b"person pixels"),)
    prompt = "Use @Image1 as the character"

    analyze_references(clip, prompt, references, images, analyzer_name="qwen", max_image_edge=384)
    analyze_references(clip, prompt, references, images, analyzer_name="qwen", max_image_edge=512)

    assert clip.generate_calls == 2


def test_alternating_reference_sets_remain_cached(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    analyzer_module._ANALYSIS_CACHE.clear()
    clip = FakeClip()
    first = (ReferenceImage("one", "person.jpg", 1, storage_name="h3studio/person.jpg"),)
    second = (ReferenceImage("two", "other.jpg", 1, storage_name="h3studio/other.jpg"),)
    analyze_references(clip, "Use @Image1", first, (FakeStableImage(1, b"person"),), analyzer_name="qwen")
    analyze_references(clip, "Use @Image1", second, (FakeStableImage(2, b"other"),), analyzer_name="qwen")
    analyze_references(clip, "Change the prompt for @Image1", first, (FakeStableImage(3, b"person"),), analyzer_name="qwen")

    assert clip.generate_calls == 2


def test_detailed_expansion_does_not_load_a_second_language_model(monkeypatch) -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    analyzer_module._ANALYSIS_CACHE.clear()
    monkeypatch.setattr(analyzer_module, "_WRITER_CACHE_KEY", None)
    monkeypatch.setattr(analyzer_module, "_WRITER_CACHE_VALUE", None)
    analyzer = FakeClip()
    writer = FakeWriter()
    references = (ReferenceImage("one", "person.jpg", 1, storage_name="h3studio/person.jpg"),)
    images = (FakeStableImage(800, b"same person pixels"),)

    _references, enhanced, note = analyze_references(
        analyzer,
        "Place @Image1 outside",
        references,
        images,
        deep_enhancement=True,
        writer_clip=writer,
        writer_name="qwen3vl_8b_fp8_scaled.safetensors",
        writer_instruction="Favor a restrained editorial lighting treatment.",
    )
    assert 180 <= len(enhanced.split()) <= 500
    assert writer.generate_calls == 0
    assert "restrained editorial lighting" in enhanced
    assert "no second language model was loaded" in note


def test_persisted_fingerprinted_description_skips_cold_reanalysis() -> None:
    import h3studio.prompting.comfy_analyzer as analyzer_module

    analyzer_module._ANALYSIS_CACHE.clear()
    analyzer = FakeClip()
    reference = ReferenceImage(
        "one",
        "person.jpg",
        1,
        storage_name="h3studio/person.jpg",
        fingerprint="persisted-fingerprint",
        description="A persisted factual description of the unchanged source image.",
        role="identity",
    )
    analyzed, _enhanced, note = analyze_references(
        analyzer,
        "Use @Image1",
        (reference,),
        (FakeStableImage(801, b"same persisted pixels"),),
    )

    assert analyzer.generate_calls == 0
    assert analyzed[0].description == reference.description
    assert "1 factual record(s) reused and 0 inspected" in note
    assert "Cache: HIT" in note
