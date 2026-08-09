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
- Optional visual analysis uses a full native ComfyUI Qwen3-VL checkpoint, is lazy and cached, and never downloads a model silently.
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

The generation panel exposes mode, aspect ratio, megapixels, seed, sampling speed, frame count, prompt shaping, and reference priority. Every non-obvious control includes a short explanation in the node. Route remains under Advanced; the separate analyzer path appears only when **Analyze images + build brief** is selected. The Director opens at a useful full height and its control panel follows manual node resizing, using internal scrolling only when the node is deliberately made small or contains many references.

## Prompt enhancement

The Director offers four prompt-shaping choices. **Keep my prompt** sends your wording unchanged apart from converting `@Image N` into H3's native `<Picture N>` labels. **Clear one-line instruction** creates a direct heading-free instruction. **Structured production brief** builds the four-section format. **Analyze images + production brief** uses the full Qwen3-VL analyzer selected in the Loader to inspect the actual reference pixels, assign roles and retention, fill each card's visible description, and then build the same strict four-section brief. Image analysis is cached when only the seed changes.

Generation modes name their model path in the UI. Text to image uses FL2VA. Image to image uses FL2VA with Image 1 as a first-frame/source anchor and preserves its canvas. Reference mix/edit uses REF2VA and treats one or more tagged images as independent sources to combine. Auto chooses text-to-image FL2VA with no references, anchored FL2VA with one reference, and REF2VA with two or more references.

`Analyze images + production brief` is the maintained workflow default when references are present. `Structured production brief` provides the deterministic no-analysis version. Both produce:

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

`Analyze images + production brief` uses ComfyUI's native full Qwen3-VL 4B implementation. The maintained workflow selects `qwen3vl_4b_fp8_scaled.safetensors` automatically when present. The model is loaded only when references actually need analysis; manual card descriptions are never overwritten.

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

No install script moves, deletes, or downloads model files. Select the models already present in your ComfyUI folders through the H3 Studio Loader.

Expected model categories:

```text
ComfyUI/models/diffusion_models/  MiniMax H3 FL2VA and REF2VA transformers
ComfyUI/models/text_encoders/     qwen3vl_32b_minimax_h3_int8_convrot.safetensors
ComfyUI/models/text_encoders/     qwen3vl_4b_fp8_scaled.safetensors (full image analyzer)
ComfyUI/models/vae/               minimax_h3_video_vae_int8_convrot.safetensors
ComfyUI/models/vae_approx/        taeh3.safetensors (optional live preview only)
ComfyUI/models/loras/             minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors
```

Exact filenames depend on the checkpoint distribution. The bundled workflow contains the filenames used by Alier's current Lightning setup; choose the actual installed entries if they differ.

The full 4B analyzer is separate because H3's 32B ConvRot checkpoint is deliberately truncated for conditioning and has no language-model head capable of writing descriptions. Both remain inside ComfyUI; LM Studio and Ollama are not involved.

### LightX v0.1 acceleration

Both four-step LightX choices load Kijai's real LightX v0.1 LoRA automatically at strength `0.8`. ER-SDE is an extended reverse-time stochastic solver; SA-Solver is a stochastic Adams multistep solver that reuses previous evaluations. Neither is universally better, so compare them with the same prompt and seed. On current ComfyUI, H3 Studio uses bypass-forward LoRA injection to avoid eagerly merging and requantizing the INT8/FP8 base model.

### Optional Mamad8 PDD REF2VA acceleration

The Director includes checkpoint-600 and checkpoint-900 Mamad8 PDD profiles as optional REF2VA four-step backends. H3 Studio does not copy or relicense Mamad8's GPL implementation. When selected, it detects the separately registered PDD nodes, loads the matching student LoRA at strength `2.0`, loads the matching heads bank at strength `1.0`, applies the trained `12/3` AV shifts, and requests Mamad8's enforced four-step Euler/trained-block schedule.

Install the external package beside H3 Studio:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8.git
```

Place the paired files from [Mamad8's model repository](https://huggingface.co/Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8) as follows:

```text
ComfyUI/models/loras/       LORA_h3_pdd_af384_step600_s.safetensors or step900
ComfyUI/models/pdd_heads/   HEADS_h3_pdd_af384_step600_bank.safetensors or step900
```

Restart ComfyUI after installing the package. Selecting PDD without the external nodes, a matching artifact pair, at least one reference, or a REF2VA route fails with a specific corrective message instead of silently falling back. Current ComfyUI uses bypass-forward LoRA injection, which avoids the multi-minute quantized merge/requantize stall; older ComfyUI builds fall back to legacy patches and print a clear warning. Base profiles remain completely independent of PDD.

For fast approximate previews during sampling, download [Kijai's TAEH3 decoder](https://huggingface.co/Kijai/MiniMax-H3-TAE/blob/main/vae_approx/taeh3.safetensors) into `ComfyUI/models/vae_approx/`, then enable the bundled **Live Preview · TAEH3** node. Leave it disabled if the file is absent. Final saving always uses the full H3 VAE.

## Same-seed A/B Matrix

The bundled workflow includes an opt-in **Same-seed A/B Matrix** for diagnosing whether quality loss comes from resolution or acceleration. It requests `0.40`, `1.00`, and `2.00 MP` using the same prompt, references, aspect ratio, frame profile, and seed. Every row compares a native no-LoRA Base profile against the selected LightX or PDD accelerator.

The node returns one labeled two-column grid. Each cell reports requested megapixels, actual aligned dimensions and megapixels, profile/LoRA status, and CUDA-synchronized time spent inside `SamplerCustomAdvanced`. Conditioning, adapter setup, VAE decode, grid composition, and queue overhead are deliberately excluded from the sampling figure. The first sampled cell can still include lazy model initialization, while later cells may benefit from warm caches, so treat the labels as honest sampler-call timings rather than a laboratory benchmark. The detailed string report exposes the same measurements for copying into an issue or experiment log.

The matrix is disabled by default because enabling it performs six complete generations. H3's native area cap can make the `1.00 MP` and `2.00 MP` rows resolve to the same actual dimensions; this is intentional and makes a misleading target-size assumption immediately visible. If the Director currently uses a Base profile, choose LightX or PDD explicitly in the matrix's accelerator control.

## Bundled workflow

`example_workflows/H3_Studio_Unified_Image.json` is generated, not hand-drifted. It preserves the visual hierarchy and spacious geometry of Alier's v1.3.7 “mine” workflow while keeping the product UI at the top level.

The workflow has four aligned normal-generation stages plus one optional benchmark stage:

1. The H3 Studio Director with integrated uploads.
2. The lazy model loader and one conditioning/route pass.
3. The reusable sampling/exact-still subgraph.
4. Preview and save output.
5. A disabled-by-default six-run same-seed A/B quality matrix.

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
- **H3 Studio · Same-Seed A/B Matrix** — six opt-in generations comparing `0.40/1.00/2.00 MP` with and without the selected accelerator, composed into one timed labeled grid.

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

State is versioned (`schema_version: 4`) and migrates old settings into typed prompt/generation sections. Schema 3 kept the safe ComfyUI storage name of an integrated upload separate from its display filename; schema 4 adds the optional PDD acceleration profiles without changing existing selections. Workflows store the full Studio state plus compatibility widget values, so the node remains inspectable even if the frontend extension is temporarily unavailable.

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PROMPTING.md](docs/PROMPTING.md), and [CONTRIBUTING.md](CONTRIBUTING.md) before changing serialization or route behavior.

## Inspiration and credit

This custom node is openly built with inspiration and code adaptation from:

- [nkxx188/ComfyUI-MiniMaxH3-Easy](https://github.com/nkxx188/ComfyUI-MiniMaxH3-Easy) for ordered virtual media links, the excellent `@Image` mention interaction, reference chips, and parts of `web/h3studio_ui.js` (MIT).
- [astropuzzo/ComfyUI-MiniMax-H3-Image-Studio](https://github.com/astropuzzo/ComfyUI-MiniMax-H3-Image-Studio) for resolution/sampling/decode/still-selection foundations and the adapted `image_runtime.py` (Unlicense).
- [mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8](https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8) for the optional external REF2VA PDD execution backend. H3 Studio calls its registered public node surface but includes none of its GPL implementation.
- Alier's private H3 Studio Unified Image Director and v1.3.7 workflow for role-aware production briefs, bridge behavior, megapixel/aspect controls, route experimentation, and the workflow's visual hierarchy.

The attribution and embedded MIT notice are preserved in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This repository is an independent project and does not claim endorsement by MiniMax, ComfyUI, or either inspiration project.

## Release policy

Private alpha releases use tags such as `v0.1.0-alpha.2`. A release archive is built from tracked source only and excludes caches, models, generated images, private reports, and local environments. CI must pass before the release workflow uploads the archive and checksums.

See [CHANGELOG.md](CHANGELOG.md) for the exact release surface.

## License

Original project code is MIT licensed. Adapted code retains its upstream license terms. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
