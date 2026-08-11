import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "example_workflows" / "H3_Studio_Unified_Image.json"
BLUEPRINT = ROOT / "subgraphs" / "H3_Studio_Sampling_and_Decode.json"
STUDIO_FRONTEND = ROOT / "web" / "js" / "studio_extension.js"


def load_workflow():
    return json.loads(WORKFLOW.read_text(encoding="utf-8"))


def test_director_is_top_level_and_sampling_is_subgraphed():
    workflow = load_workflow()
    top_types = {node["type"] for node in workflow["nodes"]}
    subgraphs = workflow["definitions"]["subgraphs"]
    assert "H3StudioDirector" in top_types
    assert len(subgraphs) == 1
    assert "H3StudioDirector" not in {node["type"] for node in subgraphs[0]["nodes"]}
    assert {"H3StudioContextSamplingPreset", "H3StudioDecode", "H3StudioFrameSelector"} <= {
        node["type"] for node in subgraphs[0]["nodes"]
    }
    assert "H3StudioTAEH3Preview" in top_types


def test_discoverable_subgraph_is_a_workflow_blueprint_envelope():
    blueprint = json.loads(BLUEPRINT.read_text(encoding="utf-8"))
    assert blueprint["version"] == 0.4
    assert len(blueprint["definitions"]["subgraphs"]) == 1
    definition = blueprint["definitions"]["subgraphs"][0]
    assert definition["state"]["lastGroupId"] == 0
    assert blueprint["nodes"][0]["type"] == definition["id"]


def test_workflow_opens_without_placeholder_images():
    workflow = load_workflow()
    director = next(node for node in workflow["nodes"] if node["type"] == "H3StudioDirector")
    links = director["properties"]["h3studio_virtual_media_links"]
    assert links == []
    assert not any(node["type"] == "LoadImage" for node in workflow["nodes"])
    serialized = json.dumps(workflow).lower()
    assert "replace me" not in serialized
    assert "image_1.png" not in serialized


def test_persisted_studio_state_is_image_only_and_versioned():
    workflow = load_workflow()
    director = next(node for node in workflow["nodes"] if node["type"] == "H3StudioDirector")
    state = json.loads(director["widgets_values"][20])
    assert state["schema_version"] == 9
    assert json.loads(director["properties"]["h3studio_state"]) == state
    assert state["prompt_options"]["enhance_mode"] == "compile_only"
    assert state["prompt_options"]["analyze_images"] is True
    assert state["prompt_options"]["deep_enhancement"] is True
    assert state["references"] == []
    assert state["generation"]["route"] == "auto"
    serialized = json.dumps(workflow).lower()
    assert "overall_soundscape" not in serialized
    assert "non_diegetic_music" not in serialized
    assert "h3 hub" not in serialized


def test_primary_graph_has_one_conditioning_pass():
    workflow = load_workflow()
    conditions = [node for node in workflow["nodes"] if node["type"] == "H3StudioCondition"]
    assert len(conditions) == 1
    assert not any(node["type"] == "CLIPTextEncode" for node in workflow["nodes"])


def test_final_png_save_receives_completed_studio_context():
    workflow = load_workflow()
    saver = next(node for node in workflow["nodes"] if node["type"] == "H3StudioSaveImage")
    context_input = next(input_slot for input_slot in saver["inputs"] if input_slot["name"] == "studio_context")
    link = next(link for link in workflow["links"] if link[0] == context_input["link"])
    assert link[1] == 10


def test_no_dead_context_inspector_is_bundled():
    workflow = load_workflow()
    assert not any(node["type"] == "H3StudioContextInspector" for node in workflow["nodes"])


def test_functional_nodes_do_not_overlap():
    workflow = load_workflow()
    functional = [node for node in workflow["nodes"] if node["type"] != "H3StudioWorkflowNote"]
    for index, left in enumerate(functional):
        lx, ly = left["pos"]
        lw, lh = left["size"]
        for right in functional[index + 1 :]:
            rx, ry = right["pos"]
            rw, rh = right["size"]
            overlap = lx < rx + rw and lx + lw > rx and ly < ry + rh and ly + lh > ry
            assert not overlap, f"{left['title']} overlaps {right['title']}"


def test_prompt_editor_and_empty_result_regression_contract():
    source = STUDIO_FRONTEND.read_text(encoding="utf-8")
    layout = (ROOT / "web" / "js" / "core" / "layout.js").read_text(encoding="utf-8")
    assert '"h3_prompt_mentions"' in source
    assert "restoreWidgetHiddenByStudio(target)" in source
    assert "].filter(Boolean);" in source
    assert "STUDIO_NODE_HEIGHT = 780" in layout
    assert "STUDIO_PANEL_HEIGHT = 530" in layout
    assert "node.onResize = function h3studioResize" not in source
    assert "Path to an instruction-capable local VLM" not in source
    assert "Image-analysis model" not in source
    assert "__H3STUDIO_REF_" not in source


def test_director_lifecycle_has_one_dispatcher_and_one_state_serializer():
    modular = STUDIO_FRONTEND.read_text(encoding="utf-8")
    legacy = (ROOT / "web" / "h3studio_ui.js").read_text(encoding="utf-8")
    for assignment in ("node.onConfigure =", "node.onSerialize =", "node.onConnectionsChange =", "node.onDrawForeground ="):
        assert assignment not in modular
    assert "this.__h3studioBeforeSerialize?.(info)" in legacy
    assert "this.__h3studioAfterSerialize?.(info)" in legacy
    assert "node.__h3studioBeforeSerialize" in modular
    assert "node.__h3studioAfterSerialize" in modular
