"""Audit custom-node registration and bundled workflow references without ComfyUI."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ROOT / "h3studio" / "extension.py",
    ROOT / "h3studio" / "nodes" / "benchmark.py",
    ROOT / "h3studio" / "nodes" / "image_runtime.py",
]


def mapping_keys(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    keys = set()
    for candidate in ast.walk(tree):
        if (
            isinstance(candidate, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "NODE_CLASS_MAPPINGS" for target in candidate.targets
            )
            and isinstance(candidate.value, ast.Dict)
        ):
            for key in candidate.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def workflow_custom_types(value):
    found = set()
    if isinstance(value, dict):
        if isinstance(value.get("type"), str) and value["type"].startswith("H3Studio"):
            found.add(value["type"])
        for nested in value.values():
            found.update(workflow_custom_types(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(workflow_custom_types(nested))
    return found


def main():
    registered = set().union(*(mapping_keys(path) for path in SOURCES))
    workflow = json.loads((ROOT / "example_workflows" / "H3_Studio_Unified_Image.json").read_text(encoding="utf-8"))
    referenced = workflow_custom_types(workflow)
    missing = referenced - registered
    if missing:
        raise SystemExit(f"Workflow references unregistered H3 Studio nodes: {sorted(missing)}")
    required = {"H3StudioDirector", "H3StudioLoader", "H3StudioCondition", "H3StudioDecode", "H3StudioFrameSelector"}
    if required - registered:
        raise SystemExit(f"Required node mappings are absent: {sorted(required - registered)}")
    if "H3StudioToImagePrepare" in registered:
        raise SystemExit("Legacy ambiguous H3StudioToImagePrepare mapping still present")
    print(
        f"Node surface is coherent: {len(registered)} registered classes; {len(referenced)} used by the bundled workflow."
    )


if __name__ == "__main__":
    main()
