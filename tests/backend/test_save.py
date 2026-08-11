import json
from types import SimpleNamespace

from h3studio.context import H3StudioContext
from h3studio.nodes.save import completed_png_metadata
from h3studio.prompting.compiler import CompileResult
from h3studio.prompting.sections import ImagePromptSections
from h3studio.references import ReferenceImage
from h3studio.resolution import ResolutionPlan
from h3studio.routing import RouteDecision
from h3studio.state import GenerationOptions, StudioState


def test_completed_png_metadata_restores_runtime_state_without_embedding_pixels():
    state = StudioState(
        prompt="Use @Image1",
        references=(
            ReferenceImage(
                id="one",
                filename="face.png",
                ordinal=1,
                storage_name="h3studio/face.png",
                description="Detailed factual description added during execution.",
            ),
        ),
        generation=GenerationOptions(seed=987, sampling_profile="base_quality_20"),
    )
    compile_result = CompileResult(
        sections=ImagePromptSections("subject", "summary", "retention", "detail"),
        rendered="rendered",
        native_prompt="Use <Picture 1>",
        resolved_mode="reference_edit",
        references=state.references,
        diagnostics=(),
    )
    context = H3StudioContext.create(
        state,
        compile_result,
        ResolutionPlan(1024, 1024, 1.0, 1.048576, "1:1", 1.0, False, None),
        RouteDecision("auto", "ref2va", "reference_edit", 1, "test"),
        images=(SimpleNamespace(shape=(1, 1024, 1024, 3)),),
        image_filenames=("face.png",),
    )
    initial = StudioState(prompt="Use @Image1").to_json()
    workflow = {
        "nodes": [{
            "type": "H3StudioDirector",
            "inputs": [{"name": "studio_state"}],
            "widgets_values": [initial],
            "properties": {"h3studio_state": initial},
        }],
    }
    prompt = {"10": {"class_type": "H3StudioDirector", "inputs": {"studio_state": initial}}}

    saved_prompt, saved_extra = completed_png_metadata(prompt, {"workflow": workflow}, context)
    restored = json.loads(saved_extra["workflow"]["nodes"][0]["properties"]["h3studio_state"])

    assert restored["references"][0]["description"].startswith("Detailed factual")
    assert restored["generation"]["seed"] == 987
    assert json.loads(saved_prompt["10"]["inputs"]["studio_state"]) == restored
    assert saved_extra["h3studio"]["reference_storage"] == ["h3studio/face.png"]
    assert saved_extra["h3studio"]["portability"] == "same_machine_storage_references"
    assert "images" not in saved_extra["h3studio"]
    assert json.loads(json.dumps(saved_extra["h3studio"]))["state"]["generation"]["seed"] == 987
