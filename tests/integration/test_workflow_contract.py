import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "example_workflows" / "H3_Studio_Unified_Image.json"


def load_workflow():
    return json.loads(WORKFLOW.read_text(encoding="utf-8"))


def test_director_is_top_level_and_sampling_is_subgraphed():
    workflow = load_workflow()
    top_types = {node["type"] for node in workflow["nodes"]}
    subgraphs = workflow["definitions"]["subgraphs"]
    assert "H3StudioDirector" in top_types
    assert len(subgraphs) == 1
    assert "H3StudioDirector" not in {node["type"] for node in subgraphs[0]["nodes"]}
    assert {"H3StudioSamplingPreset", "H3StudioDecode", "H3StudioFrameSelector"} <= {
        node["type"] for node in subgraphs[0]["nodes"]
    }


def test_workflow_stores_nine_image_capacity_and_three_ordered_examples():
    workflow = load_workflow()
    director = next(node for node in workflow["nodes"] if node["type"] == "H3StudioDirector")
    links = director["properties"]["h3studio_virtual_media_links"]
    assert [item["source_id"] for item in links] == [1, 2, 3]
    assert [item["order"] for item in links] == [1, 2, 3]
    assert all(item["media_type"] == "image" for item in links)


def test_persisted_studio_state_is_image_only_and_versioned():
    workflow = load_workflow()
    director = next(node for node in workflow["nodes"] if node["type"] == "H3StudioDirector")
    state = json.loads(director["widgets_values"][20])
    assert state["schema_version"] == 2
    assert len(state["references"]) == 3
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
