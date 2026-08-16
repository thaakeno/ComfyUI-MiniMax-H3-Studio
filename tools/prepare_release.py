"""Prepare a prerelease request without leaving tracked version metadata stale."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^(?P<base>\d+\.\d+\.\d+)-alpha\.(?P<serial>\d+)$")


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Could not update version in {path.relative_to(ROOT)}")
    path.write_text(updated, encoding="utf-8")


def render_changelog(version: str, date: str, sections: dict[str, list[str]]) -> str:
    lines = [f"## [{version}] - {date}", ""]
    for heading in ("Added", "Fixed", "Changed"):
        items = sections.get(heading.lower(), [])
        if not items:
            continue
        lines.extend([f"### {heading}", ""])
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n\n"


def update_readme_release_pin(version: str) -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"git clone --branch v\d+\.\d+\.\d+-alpha\.\d+ --depth 1",
        f"git clone --branch v{version} --depth 1",
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not update the pinned release clone command in README.md")
    if '<div align="center">' not in updated[:256] and "\n</div>" in updated:
        updated = updated.replace(
            "\n# MiniMax H3 Studio",
            '\n<div align="center">\n\n# MiniMax H3 Studio',
            1,
        )
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    request_path = ROOT / (sys.argv[1] if len(sys.argv) > 1 else ".github/release-request.json")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    version = str(request["version"]).strip()
    match = VERSION_RE.fullmatch(version)
    if not match:
        raise SystemExit(f"Unsupported prerelease version: {version}")
    py_version = f"{match.group('base')}a{match.group('serial')}"

    # Keep the raw SemVer prerelease spelling in pyproject.toml because the
    # Comfy Registry validates this field as semantic versioning. Python's
    # packaging stack accepts the same string and normalizes it to `aN`.
    replace_once(ROOT / "pyproject.toml", r'^version\s*=\s*"[^"]+"$', f'version = "{version}"')
    replace_once(ROOT / "h3studio/constants.py", r'^VERSION:\s*Final\s*=\s*"[^"]+"$', f'VERSION: Final = "{version}"')

    package_path = ROOT / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = version
    package_path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    update_readme_release_pin(version)

    changelog_path = ROOT / "CHANGELOG.md"
    changelog = changelog_path.read_text(encoding="utf-8")
    heading = f"## [{version}]"
    if heading not in changelog:
        marker = "\n## ["
        offset = changelog.find(marker)
        if offset < 0:
            raise SystemExit("CHANGELOG.md has no version insertion point")
        entry = render_changelog(version, str(request["date"]), request.get("sections", {}))
        changelog = changelog[: offset + 1] + entry + changelog[offset + 1 :]
        changelog_path.write_text(changelog, encoding="utf-8")

    subprocess.run(["uv", "lock"], cwd=ROOT, check=True)
    print(f"Prepared {version} ({py_version} when normalized by Python packaging) and refreshed uv.lock")


if __name__ == "__main__":
    main()
