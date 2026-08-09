"""Fail closed when the tracked source is not suitable for a private release."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".js", ".json", ".md", ".toml", ".txt", ".yml", ".yaml"}
FORBIDDEN_SUFFIXES = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}
SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
]


def command(*args):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout


def tracked_files():
    return [ROOT / value for value in command("git", "ls-files").splitlines() if value]


def main():
    errors = []
    files = tracked_files()
    required = [
        "README.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "example_workflows/H3_Studio_Unified_Image.json",
        "subgraphs/H3_Studio_Sampling_and_Decode.json",
        ".github/workflows/ci.yml",
        ".github/workflows/release.yml",
    ]
    tracked_relative = {path.relative_to(ROOT).as_posix() for path in files}
    for required_path in required:
        if required_path not in tracked_relative:
            errors.append(f"required release file is not tracked: {required_path}")
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"model/binary artifact is tracked: {relative}")
        if path.stat().st_size > 5_000_000:
            errors.append(f"tracked file exceeds 5 MB: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE", ".gitignore", ".comfyignore"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"tracked text file is not UTF-8: {relative}")
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible credential in {relative}: {pattern.pattern[:24]}")
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = metadata["project"]["version"]
    display_version = re.sub(r"a(\d+)$", r"-alpha.\1", version)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if version not in changelog and display_version not in changelog:
        errors.append(f"project version {version} ({display_version}) is absent from CHANGELOG.md")
    workflow = json.loads((ROOT / "example_workflows" / "H3_Studio_Unified_Image.json").read_text(encoding="utf-8"))
    if workflow.get("extra", {}).get("h3studio", {}).get("hub_included") is not False:
        errors.append("workflow does not explicitly exclude H3 Hub")
    if errors:
        raise SystemExit("Release check failed:\n- " + "\n- ".join(errors))
    total_bytes = sum(path.stat().st_size for path in files)
    print(f"Release source is clean: {len(files)} tracked files, {total_bytes / 1024:.1f} KiB, version {version}.")


if __name__ == "__main__":
    main()
