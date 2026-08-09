# ComfyUI MiniMax H3 Studio

MiniMax H3 Studio is a still-image production surface for ComfyUI: one reference-aware Director, a lazy dual-route model loader, deterministic production-brief prompting, optional local VLM analysis, exact temporal-packet decoding, and a maintained workflow that remains understandable after you open it.

The project is intentionally image-only. It does not include H3 Hub, App Mode, an installer, audio controls, or fake sound fields in image prompts.

> Status: **private alpha**. Pure logic, serialization, frontend syntax, and workflow structure are tested locally. Actual H3 CUDA generation must still be smoke-tested in the target Lightning.ai ComfyUI environment.

## What it fixes

The original experiments proved that MiniMax H3 can produce strong stills through its short temporal latent, but the editing experience was fragmented. Easy supplied the best `@Image` interaction but not the full still-image direction system. Image Studio supplied careful resolution, sampling, decode, and selection tools but used a different interaction model. The private Unified Image Director added useful role-aware prompt compilation and routing, while its monolithic UI and bridge arrangement were hard to maintain.

This repository keeps the strongest parts and changes the architecture:

- `@Image 1` through `@Image 9` are first-class, ordered references with real mention chips.
- Every image has a filename, role, retention policy, and optional natural-language definition.
- Text-to-image works with no reference attached.
- Aspect ratio and megapixels resolve to H3-safe dimensions aligned to 32.
- Prompt compilation emits only `subject_definitions`, `summary`, `retention_analysis`, and `detailed_description`.
- Optional VLM analysis is explicit, local, and never downloads a model silently.
- FL2VA and REF2VA remain observable routes instead of an unproven REF2VA-only assumption.
- The Qwen3-VL encoder is used once in H3 conditioning; the Studio compiler does not duplicate that expensive pass.
- Exact decode preserves the requested temporal packet before selecting a single still.
- The custom DOM Director stays top-level; stable sampling and decode plumbing live in a reusable subgraph.

## Studio Director

Click **Add images** inside the Director to upload up to nine references directly into ComfyUI. Each successful upload immediately becomes an ordered card with a real thumbnail and `@Image N` identity. No external loader is required, no placeholder is treated as a reference, and the workflow opens at `0/9` ready for text-to-image. Existing `Load Image` outputs can still be connected to the Director's `Media` dot when an advanced graph needs them.

| Control | Meaning |
| --- | --- |
| Role | What the image defines: identity, style, composition, pose, outfit, typography, lighting, and more |
| Retention | `fully_preserved`, `attribute_transfer`, `partially_preserved`, or `reference_only` |
| Description | A precise instruction such as “exact face and blond spiky hair” |
| Order | The stable ordinal used by `@Image N` |

Type `@` in the prompt editor to insert a reference. Reordering cards updates their runtime order without depending on filename guesses. Removing all images leaves a valid text-to-image request.

The generation panel exposes mode, aspect ratio, megapixels, seed, prompt enhancement, and adherence. Route, sampling profile, frame profile, and optional analyzer path are available under Advanced.

## Prompt enhancement

`Production brief` is the safe default. It deterministically converts the user's request and reference metadata into:

```text
subject_definitions:
@Image 1 defines the exact subject identity and facial structure.
@Image 2 defines the rendering style and color treatment.

summary:
[image generation] A concise statement of the requested final image.

retention_analysis:
@Image 1: fully_preserved - identity details must remain exact.
@Image 2: attribute_transfer - apply style without copying scene content.

detailed_description:
A coherent natural-language production brief preserving the user's intent.
```

`VLM analysis + brief` can use a separately selected local instruction-capable vision-language model through Transformers. It may inspect the attached images and draft richer definitions before the deterministic compiler enforces the four-section contract. The model path is explicit, automatic downloading is disabled, and the analyzer unloads by default.

The `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` loaded with ComfyUI's `CLIPLoader`/MiniMax path remains H3's multimodal conditioning encoder. A ConvRot encoder checkpoint is not assumed to expose a general autoregressive chat interface, so it is not silently treated as the separate prompt writer.

## Routing

The default is `auto`:

| Request | Selected route |
| --- | --- |
| No images | FL2VA text-to-image |
| One image, image-to-image intent | FL2VA first-frame anchor |
| Multi-reference/edit intent | REF2VA |

Forced `fl2va` and `ref2va` controls exist for controlled comparisons. Diagnostics explicitly report the selected path and when a forced path ignores additional images. REF2VA-only text-to-image remains experimental until it wins a real Lightning comparison.

## Installation on Lightning.ai

From the ComfyUI custom nodes directory:

```bash
git clone git@github.com:thaakeno/ComfyUI-MiniMax-H3-Studio.git
cd ComfyUI-MiniMax-H3-Studio
pip install -r requirements.txt
```

Restart ComfyUI and open `example_workflows/H3_Studio_Unified_Image.json`.

For optional local VLM analysis:

```bash
pip install -e ".[vlm]"
```

No install script moves, deletes, or downloads model files. Select the models already present in your ComfyUI folders through the H3 Studio Loader.

Expected model categories:

```text
ComfyUI/models/diffusion_models/  MiniMax H3 FL2VA and REF2VA transformers
ComfyUI/models/text_encoders/     qwen3vl_32b_minimax_h3_int8_convrot.safetensors
ComfyUI/models/vae/               minimax_h3_video_vae_int8_convrot.safetensors
ComfyUI/models/vae_approx/        taeh3.safetensors (optional live preview only)
```

Exact filenames depend on the checkpoint distribution. The bundled workflow contains the filenames used by Alier's current Lightning setup; choose the actual installed entries if they differ.

For fast approximate previews during sampling, download [Kijai's TAEH3 decoder](https://huggingface.co/Kijai/MiniMax-H3-TAE/blob/main/vae_approx/taeh3.safetensors) into `ComfyUI/models/vae_approx/`, then enable the bundled **Live Preview · TAEH3** node. Leave it disabled if the file is absent. Final saving always uses the full H3 VAE.

## Bundled workflow

`example_workflows/H3_Studio_Unified_Image.json` is generated, not hand-drifted. It preserves the visual hierarchy and spacious geometry of Alier's v1.3.7 “mine” workflow while keeping the product UI at the top level.

The workflow has four aligned visible stages:

1. The H3 Studio Director with integrated uploads.
2. The lazy model loader and one conditioning/route pass.
3. The reusable sampling/exact-still subgraph.
4. Preview and save output.

`subgraphs/H3_Studio_Sampling_and_Decode.json` is also supplied independently. It contains only typed sampling, decode, and still-selection plumbing. This is deliberate: ComfyUI does not reliably promote a custom DOM mention editor through subgraph widgets, while native typed sockets remain stable.

Regenerate and validate both files with:

```bash
python tools/generate_workflows.py
python tools/generate_workflows.py --check
python tools/validate_workflows.py
```

## Nodes

The normal path uses:

- **H3 Studio · Image Director** — ordered images, `@` mentions, production brief, resolution, seed, and route intent.
- **H3 Studio · Model Loader** — Qwen encoder and VAE loading with lazy FL2VA/REF2VA transformer switching.
- **H3 Studio · Condition & Route** — compiles and encodes once, prepares the H3 latent, and selects the model route.
- **H3 Studio · Sampling Preset** — conservative base recipes and clearly marked experimental turbo recipes.
- **H3 Studio · Exact Frame Decode** — decodes the complete selected temporal profile.
- **H3 Studio · Single Image Output** — fixed or metric-based still selection with an inspectable report.

Advanced and compatibility nodes are documented in [docs/NODES.md](docs/NODES.md).

## Verification

Local checks:

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check h3studio tests/backend tools
npm run check
python tools/generate_workflows.py --check
python tools/validate_workflows.py
python tools/audit_nodes.py
python tools/release_check.py
```

These checks do not prove GPU generation. Run the concise [Lightning smoke-test plan](docs/LIGHTNING_TEST_PLAN.md) against the exact ComfyUI installation and model files before promoting a release from alpha.

## Design and maintenance

The backend is split into state, references, resolution, routing, prompt sections, templates, VLM adapter, loader, and node modules. Frontend additions are split into state, DOM helpers, theme, and Studio controls. The adapted Easy mention runtime remains isolated so future upstream comparison is possible.

State is versioned (`schema_version: 3`) and migrates old settings into typed prompt/generation sections. Schema 3 keeps the safe ComfyUI storage name of an integrated upload separate from its display filename. Workflows store the full Studio state plus compatibility widget values, so the node remains inspectable even if the frontend extension is temporarily unavailable.

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PROMPTING.md](docs/PROMPTING.md), and [CONTRIBUTING.md](CONTRIBUTING.md) before changing serialization or route behavior.

## Inspiration and credit

This custom node is openly built with inspiration and code adaptation from:

- [nkxx188/ComfyUI-MiniMaxH3-Easy](https://github.com/nkxx188/ComfyUI-MiniMaxH3-Easy) for ordered virtual media links, the excellent `@Image` mention interaction, reference chips, and parts of `web/h3studio_ui.js` (MIT).
- [astropuzzo/ComfyUI-MiniMax-H3-Image-Studio](https://github.com/astropuzzo/ComfyUI-MiniMax-H3-Image-Studio) for resolution/sampling/decode/still-selection foundations and the adapted `image_runtime.py` (Unlicense).
- Alier's private H3 Studio Unified Image Director and v1.3.7 workflow for role-aware production briefs, bridge behavior, megapixel/aspect controls, route experimentation, and the workflow's visual hierarchy.

The attribution and embedded MIT notice are preserved in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This repository is an independent project and does not claim endorsement by MiniMax, ComfyUI, or either inspiration project.

## Release policy

Private alpha releases use tags such as `v0.1.0-alpha.2`. A release archive is built from tracked source only and excludes caches, models, generated images, private reports, and local environments. CI must pass before the release workflow uploads the archive and checksums.

See [CHANGELOG.md](CHANGELOG.md) for the exact release surface.

## License

Original project code is MIT licensed. Adapted code retains its upstream license terms. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
