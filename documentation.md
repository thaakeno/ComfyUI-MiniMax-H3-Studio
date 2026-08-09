# Operator runbook

This runbook tracks the repository as implemented. It begins as a build-time control document and will be tightened before release.

## Environment

Development and static verification run locally on Windows with Python 3.11 and Node.js. Full MiniMax H3 execution runs later in ComfyUI on Lightning.ai through VS Code.

## Verification entry points

```powershell
python -m pytest -q
npm test
python tools/validate_workflows.py
python tools/release_check.py
```

## Validation boundary

Local checks cover deterministic prompt compilation, reference indexing, resolution calculation, state migration, frontend behavior under a harness, node registration, workflow topology and release packaging. They do not prove CUDA compatibility, model memory behavior, sampling quality or final ComfyUI rendering.

## Repository map

Runtime Python lives under `h3studio/`, browser code under `web/`, workflows under `example_workflows/` and `subgraphs/`, tests under `tests/`, documentation under `docs/`, and release/validation utilities under `tools/`.

## Verification ledger

- Backend and integration: 92 passed.
- Frontend state, migration, upload-storage, mention, and resolution: nine passed.
- Python compilation, Ruff, JavaScript syntax, whitespace, and local-import checks: passed.
- Workflow regeneration and topology validation: passed; 13 aligned top-level nodes, six subgraph nodes, no placeholder loaders, dead inspector, or functional-node overlap.
- Registration audit: passed; 16 registered H3 Studio classes and seven used by the maintained workflow.
- Release-source audit: passed; no model artifacts or detected credentials.
- CUDA generation and image-quality comparison: intentionally deferred to `docs/LIGHTNING_TEST_PLAN.md`.
