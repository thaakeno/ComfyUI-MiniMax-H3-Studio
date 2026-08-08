# Contributing

Keep changes small enough to review and preserve the working reference interaction. The repository deliberately separates the adapted Easy mention runtime, modular Studio controls, pure Python logic, ComfyUI runtime adapters, and generated workflow.

## Development setup

```bash
uv sync --extra dev
npm run check
uv run pytest -q
```

ComfyUI itself is not installed as a package dependency. Pure logic tests run outside ComfyUI; runtime/GPU behavior is verified in a real ComfyUI checkout using [docs/LIGHTNING_TEST_PLAN.md](docs/LIGHTNING_TEST_PLAN.md).

## Rules

- Do not add silent model downloads or filesystem mutation.
- Do not merge H3 Hub, installation, cloud orchestration, video, or audio features into this image package.
- Preserve state migration whenever a serialized field changes.
- Keep `@Image N` friendly syntax distinct from the `<Picture N>` runtime syntax.
- Do not encode the H3 prompt twice.
- Keep forced REF2VA text-to-image experimental until measured output supports changing the default.
- Do not manually edit generated workflow JSON without updating `tools/generate_workflows.py`.
- Preserve third-party notices around adapted code.

## Before committing

```bash
uv run pytest -q
uv run ruff check h3studio tests/backend tools
npm run check
python tools/generate_workflows.py --check
python tools/validate_workflows.py
python tools/audit_nodes.py
python tools/release_check.py
```

For a runtime change, also record the ComfyUI version, frontend version, selected model filenames, GPU, mode, number of references, route diagnostic, output dimensions, and whether a still was saved successfully.
