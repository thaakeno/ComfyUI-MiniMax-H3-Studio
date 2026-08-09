# Execution plan

## Product boundary

The repository owns H3 still-image direction, reference organization, prompt compilation, conditioning preparation, sampling presets, frame extraction, workflow templates, and frontend interaction. It does not own H3 Hub, model installation, Lightning orchestration, cloud storage, or video/audio production.

## Architecture

The visible `H3 Studio Director` node owns the user-facing prompt and ordered media state. The browser extension renders the media cards, mention menu, compact controls, validation, and serialization. Python receives a versioned state payload and emits a typed `H3_STUDIO_CONTEXT` plus inspectable text and dimensions.

Small backend nodes consume that context for prompt enhancement, H3 conditioning, routing, sampling-profile selection, still decoding, and frame selection. The complete workflow keeps the Director visible at the top level and places ordinary plumbing inside reusable subgraphs. This avoids relying on promoted custom DOM widgets, while width, height, seed, megapixels, and aspect ratio remain explicit and inspectable.

The VLM enhancer is optional and adapter-based. It must never silently download a model. The default deterministic compiler remains fully usable without Transformers. Image-mode enhancement emits only `subject_definitions`, `summary`, `retention_analysis`, and `detailed_description`.

## Milestone 1 — repository and contracts

Scope: repository skeleton, control documents, license and attribution policy, package metadata, architecture contracts, fixture strategy.

Acceptance criteria:

- Local Git repository exists on `main`.
- H3 Hub and audio prompting are explicitly excluded.
- Provenance and licensing boundaries are documented.
- First checkpoint commit is clean.

Verification:

```powershell
git status --short
python -m compileall .
```

## Milestone 2 — backend foundation

Scope: typed state, reference normalization, mention parsing, role inference, prompt sections, resolution math, modes, errors, serialization and core controller nodes.

Acceptance criteria:

- `@Image N` references compile deterministically.
- Missing references produce actionable diagnostics instead of crashes.
- Dimensions are multiples of 32 and obey the selected MP/aspect policy.
- T2I is valid with zero references.
- Structured image prompts contain exactly four sections.

Verification:

```powershell
python -m pytest tests/backend -q
python -m compileall h3studio
```

## Milestone 3 — H3 runtime nodes

Scope: ComfyUI adapters, conditioning, reference loading, route selection, sampling profiles, model patching policy, decode and still-frame selection.

Acceptance criteria:

- Imports degrade cleanly outside ComfyUI.
- No duplicate text-encoder pass is introduced by the Studio context.
- Routing is explicit and observable.
- Experimental turbo behavior is opt-in and versioned.
- Runtime nodes expose useful previews and diagnostics.

Verification:

```powershell
python -m pytest tests/backend tests/integration -q
python tools/audit_nodes.py
```

## Milestone 4 — frontend Studio UI

Scope: modular JavaScript extension, semantic theme tokens, node shell, prompt editor, mention popup, media cards, reorder/remove/role controls, resolution controls, state migration and accessibility.

Acceptance criteria:

- No monolithic frontend file.
- Mention insertion works at the caret and respects ordered references.
- Media reorder rewrites mentions safely.
- State round-trips across workflow serialization.
- T2I disables irrelevant reference requirements.
- Keyboard paths exist for media actions and the mention menu.

Verification:

```powershell
npm test
npm run lint
```

## Milestone 5 — workflows and subgraphs

Scope: full styled workflow based on the geometry and visual hierarchy of Alier's v1.3.7 workflow, reusable subgraph blueprints, template metadata, workflow generator and validator.

Acceptance criteria:

- Primary UI workflow is approximately 2,000 meaningful JSON lines.
- Director remains top-level and visually prominent.
- Sampling/decode plumbing is grouped and reusable.
- Workflow imports contain no stale node IDs or broken links.
- Seed, aspect ratio and megapixels remain visible and connected.

Verification:

```powershell
python tools/generate_workflows.py --check
python tools/validate_workflows.py
```

## Milestone 6 — release-quality repository

Scope: README, node docs, compatibility matrix, examples, changelog, contribution guide, CI, release workflow, registry metadata, install and troubleshooting guidance.

Acceptance criteria:

- README openly credits all three inspirations.
- License notices are preserved.
- Release automation builds a clean source archive.
- Documentation distinguishes local verification from Lightning GPU validation.

Verification:

```powershell
python tools/release_check.py
```

## Milestone 7 — final audit and private push

Scope: complete verification, code/JSON line audit, history review, private GitHub creation and push.

Acceptance criteria:

- All available tests pass.
- Repository contains multiple meaningful milestone commits.
- No credentials, model files, generated outputs or private reports are committed.
- GitHub visibility is `PRIVATE`.
- Local `main` matches `origin/main`.

Verification:

```powershell
python -m pytest -q
npm test
python tools/release_check.py
git status --short
git log --oneline --decorate -12
gh repo view --json visibility,url
```

## Risk register

ComfyUI frontend APIs change frequently. Mitigation: isolate framework hooks, version the state schema, test serialization, and document a tested compatibility band.

The user's ConvRot Qwen3-VL encoder may not support autoregressive text generation. Mitigation: keep prompt enhancement behind an adapter and support a separate explicitly selected instruction model without automatic downloads.

REF2VA-only T2I quality is not established. Mitigation: preserve explicit `auto`, `t2i_fl2va`, and `reference_ref2va` routes until Lightning comparisons settle the default.

GPU execution is unavailable locally. Mitigation: validate pure logic, schemas, import behavior and workflow structure here; provide an exact Lightning smoke-test checklist; never label CUDA generation as verified before it runs there.

Subgraph widget promotion remains unstable. Mitigation: keep the custom Studio UI on its real node and subgraph only native plumbing.

## Decision log

- Image prompts use four sections only; audio sections are omitted.
- H3 Hub is not part of the package.
- No App Mode dependency.
- No silent downloads or network calls during node execution.
- Runtime behavior wins over line-count targets; generated workflow formatting remains deterministic.

## Completion record

Milestones 1–7 and the alpha-2 uploader correction are complete locally. The source has 9,747 custom-node runtime lines, a clean 1,840-line primary workflow, and a 718-line reusable sampling/decode subgraph. Lightning CUDA validation is an explicit environment smoke test, not unfinished repository implementation.
