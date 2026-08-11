"""Structural validation for bundled ComfyUI workflows."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("H3 Hub", "overall_soundscape", "non_diegetic_music", "audio_vae")


def validate_graph(graph, label: str, *, subgraph=False):
    errors = []
    nodes = graph.get("nodes", [])
    ids = [node.get("id") for node in nodes]
    if len(ids) != len(set(ids)):
        errors.append(f"{label}: duplicate node ids")
    node_map = {node["id"]: node for node in nodes}
    links = graph.get("links", [])
    normalized = [
        (link[0], link[1], link[2], link[3], link[4], link[5])
        if isinstance(link, list)
        else (link["id"], link["origin_id"], link["origin_slot"], link["target_id"], link["target_slot"], link["type"])
        for link in links
    ]
    link_ids = [link[0] for link in normalized]
    if len(link_ids) != len(set(link_ids)):
        errors.append(f"{label}: duplicate link ids")
    for link_id, origin, origin_slot, target, target_slot, kind in normalized:
        if origin not in node_map and not (subgraph and origin == -10):
            errors.append(f"{label}: link {link_id} missing origin {origin}")
        if target not in node_map and not (subgraph and target == -20):
            errors.append(f"{label}: link {link_id} missing target {target}")
        if origin in node_map and origin_slot >= len(node_map[origin].get("outputs", [])):
            errors.append(f"{label}: link {link_id} origin slot {origin_slot} out of range")
        if target in node_map and target_slot >= len(node_map[target].get("inputs", [])):
            errors.append(f"{label}: link {link_id} target slot {target_slot} out of range")
        if not kind:
            errors.append(f"{label}: link {link_id} has no type")
    text = json.dumps(graph, ensure_ascii=False)
    for token in FORBIDDEN:
        if token.lower() in text.lower():
            errors.append(f"{label}: forbidden image-workflow token {token!r}")
    return errors


def main():
    path = ROOT / "example_workflows" / "H3_Studio_Unified_Image.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_graph(workflow, path.name)
    subgraphs = workflow.get("definitions", {}).get("subgraphs", [])
    if len(subgraphs) != 1:
        errors.append(f"{path.name}: expected exactly one maintained subgraph")
    for subgraph in subgraphs:
        errors.extend(validate_graph(subgraph, f"subgraph:{subgraph.get('name')}", subgraph=True))
    node_types = {node.get("type") for node in workflow.get("nodes", [])}
    required = {
        "H3StudioDirector",
        "H3StudioLoader",
        "H3StudioCondition",
        "PreviewImage",
        "H3StudioSaveImage",
    }
    missing = required - node_types
    if missing:
        errors.append(f"{path.name}: missing required nodes {sorted(missing)}")
    if "LoadImage" in node_types:
        errors.append(f"{path.name}: bundled workflow must not contain required placeholder LoadImage nodes")
    if "H3StudioContextInspector" in node_types:
        errors.append(f"{path.name}: bundled workflow contains an unconsumed inspector node")
    functional = [node for node in workflow.get("nodes", []) if node.get("type") != "H3StudioWorkflowNote"]
    for index, left in enumerate(functional):
        lx, ly = left["pos"]
        lw, lh = left["size"]
        for right in functional[index + 1 :]:
            rx, ry = right["pos"]
            rw, rh = right["size"]
            if lx < rx + rw and lx + lw > rx and ly < ry + rh and ly + lh > ry:
                errors.append(f"{path.name}: functional nodes overlap: {left['title']!r} and {right['title']!r}")
    serialized = json.dumps(workflow, ensure_ascii=False).lower()
    for placeholder in ("replace me", "image_1.png", "image_2.png", "image_3.png"):
        if placeholder in serialized:
            errors.append(f"{path.name}: placeholder content remains: {placeholder!r}")
    lines = path.read_text(encoding="utf-8").count("\n")
    if not 1800 <= lines <= 2800:
        errors.append(f"{path.name}: expected 1,800-2,800 meaningful lines, got {lines}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(
        f"Workflow graph is structurally valid: {len(workflow['nodes'])} top-level nodes, {len(subgraphs[0]['nodes'])} subgraph nodes, {lines:,} lines."
    )


if __name__ == "__main__":
    main()
