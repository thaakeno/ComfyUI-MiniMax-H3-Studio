# Changelog

All notable changes are recorded here. The format follows Keep a Changelog; versions use semantic versioning with prerelease identifiers while Lightning GPU validation is incomplete.

## [0.1.0-alpha.12] - 2026-08-11

### Added

- Added a guarded multi-profile Benchmark Lab with profile, resolution, VAE, repeat, and seed axes; live progress; honest ETA; optional cell previews; and comparison sheets containing useful source and result metadata.
- Added a persisted Director comparison toggle and dedicated comparison node that place labeled `@ImageN` references beside the generated result and mirror the sheet back into the Director.
- Added finished-image presentation and real seed-aware rerun actions in the Director, polished Markdown workflow cards, direct model-download links, and a public privacy-preserving aggregate generation badge.
- Added direct 0.2–8.5 MP controls with conservative/recommended and experimental presentation, aligned output dimensions, and separately selectable decode/frame profiles.

### Fixed

- Repaired lazy Normal/Benchmark routing, early invalid-route validation, generated-PNG restoration, workflow persistence, reference metadata/thumbnails, subgraph packaging, node geometry, and unlocked/locked seed behavior.
- Separated factual image-analysis, prompt-writer, reference, VAE, and latent caches; profile and LoRA changes now reuse unchanged Qwen work instead of regenerating it.
- Repaired malformed/truncated analyzer output, factual descriptions, reference role/ownership inference, legacy `@Image` syntax, deterministic H3 prompt compilation, and visible rich reference pills.
- Moved TAEH3 decoding into the active sampler lifetime, corrected packed-latent reconstruction, and surfaced preview failures in the node UI.
- Connected successful H3 Studio image saves to the aggregate counter and count real batch sizes without collecting generation content or identifiers.

### Changed

- Preserved the proven direct multi-megapixel path from the earlier resolution work and labels very high resolutions as experimental rather than implying guaranteed quality.
- Aligned LightX metadata with its empirical Kijai recipe, feature-detected compatible upstream chunked H3 VAE decoding, and retained the proven staged conditioning/NVFP4 path without manual DynamicVRAM eviction.
- Rebuilt the maintained workflow as template `1.6.0` with a clearer generation, preview, output, and benchmark layout plus recommended and optional model download cards.
- Reworked prompt results to distinguish the exact runtime instruction, one-line instruction, structured production brief, and editable Qwen source direction.

## [0.1.0-alpha.11] - 2026-08-09

### Added

- Added two independent Benchmark Lab profile selectors, enabling Base-vs-LoRA and direct LightX-vs-PDD/LoRA-vs-LoRA comparisons.
- Added an optional Mamad8 T=1 Image VAE selector and an identical-latent VAE decoder A/B mode; normal multi-frame decoding remains on the original H3 video VAE.
- Added the experimental single-frame Image VAE profile, complete `hf download` installation instructions, and workflow notes covering model sources, upscaling, outpainting, and the current inpainting boundary.

### Fixed

- Removed the A/B crash when “Director selected accelerator” resolved to a Base profile; Base is now a valid comparison profile instead of an error after expensive prompt analysis.
- Replaced the subgraph `ExecutionBlocker` gate with ComfyUI's official lazy-image switch, so benchmark mode cannot schedule a seventh normal generation.
- Repaired generic visual-analyzer role assignments from prompt grammar after pixel analysis; person/character sources and object/style/outfit donors now update auto-managed role and retention controls correctly.
- Promoted holding/carrying requests into validated visible contact geometry instead of allowing an object to float independently in front of the subject.
- Accepted valid 180+ word 4B writer results instead of wasting a second generation solely because they fell slightly below the former arbitrary 250-word threshold.

### Changed

- Grouped matrix execution by profile to reduce repeated adapter swapping and reused identical native-capped variants when profile, seed, prompt, and actual canvas match.
- Renamed and clarified the detailed prompt-expansion control; the maintained workflow keeps it enabled, while intentionally disabling it now clearly explains the shorter 40–90 word result.
- Replaced the private-development README with a shorter public-ready guide while preserving inspiration, license boundaries, verification commands, and model links.

## [0.1.0-alpha.10] - 2026-08-09

### Added

- Added an optional cached text-only prompt-director pass that reuses the full Qwen3-VL analyzer by default, supports a separately selected full 8B checkpoint, targets 250-500 words, validates assignments and hard constraints, retries once, and has a complete deterministic fallback.
- Added fixed, paired-row, and per-image seed strategies to the A/B Matrix; every generated cell and report line now displays its actual seed.
- Added all model and optional-backend source links directly to the maintained workflow.

### Fixed

- Split factual pixel inspection from creative prompt expansion so source descriptions no longer need to carry the entire production-writing job.
- Gated the normal sampling branch through the A/B node, so enabling a six-cell matrix no longer triggers an unwanted seventh generation.
- Bumped state schema to 8 while preserving the old one-pass behavior for existing saved workflows.

## [0.1.0-alpha.9] - 2026-08-09

### Fixed

- Made the visible seed follow ComfyUI's hidden `control_after_generate` widget, so Randomize advances and remains visible after every queue instead of being overwritten by stale Studio state.
- Turned gaze and head-direction requests such as “look to the right” into explicit frame-right/frame-left hard constraints that override a reference image's original frontal pose.
- Replaced quantized LoRA weight merging with ComfyUI's bypass-forward adapter path for LightX and PDD when supported, avoiding the multi-minute merge/requantize initialization seen with INT8/FP8 H3 models.
- Made both LightX profiles load Kijai's actual LightX v0.1 LoRA instead of applying only a four-step sampling schedule.

### Added

- Added lazy native ComfyUI Qwen3-VL 4B visual analysis. It inspects the actual reference tensors, assigns role and retention, writes visible descriptions into the image cards, and caches analysis across seed-only reruns.
- Added the full analyzer selector to H3 Studio Loader and wired its bundle directly into the Director in the maintained workflow.
- Added accurate in-node explanations for ER-SDE, SA-Solver, LightX adapter loading, and PDD's accelerated adapter backend.

## [0.1.0-alpha.8] - 2026-08-09

### Fixed

- Fixed TAEH3 live preview's sampler wrapper calling the current wrapper index recursively; it now advances through ComfyUI's wrapper chain exactly once per sample and reuses one preview-enabled model instead of accumulating wrappers across queues.
- Matched the known-working Smart Multi-Ref REF2VA conditioning contract by attaching `minimax_frame_count` together with ordered reference latents.
- Stopped production briefs from turning every reference into a separate `<Subject N>`, which could make H3 reproduce source panels, cutouts, floating clothing, or duplicate bodies instead of synthesizing one result.
- Normalized `@image_1`, raw/underscored H3 Studio runtime tokens, Markdown-escaped mention tokens, and zero-width editor text into stable `<Picture N>` references.
- Made one-reference Auto mode compile as a locked FL2VA source edit with full preservation of every unmentioned property.

### Added

- Added **Clear one-line instruction**, a heading-free prompt mode for direct edits and reference combinations with explicit role, preservation, and anti-collage rules.
- Added subtle mode descriptions that state exactly when Auto, Text to image, Image to image, and Reference mix/edit use FL2VA or REF2VA.
- Added prompt-managed role and retention controls: inferred values are written back into both dropdowns, remain auto-updatable on later prompts, show a visual cue, and are printed as auto/manual in the execution report.
- Added bounded in-node caches for unchanged conditioning and PDD patch preparation, avoiding repeat Qwen3-VL/reference-VAE encoding and repeat LoRA/heads patch construction when only the seed changes.
- Added plain-language retention explanations and detailed help for every Base, LightX, and PDD speed profile.

### Changed

- **Keep my prompt** now truly preserves the user's wording and only converts friendly image mentions; it no longer silently builds the four-section brief.
- Structured briefs now use direct `<Picture N>` role contracts, preserve the user's operation as the final-image instruction, and explicitly require a single coherent result.

## [0.1.0-alpha.7] - 2026-08-09

### Fixed

- Converted Easy-derived rich-editor runtime tokens back into canonical `@Image N` references before compilation, with a backend repair path for already-serialized `__H3STUDIO_REF_N__` prompts and zero-width chip spacing.
- Isolated role inference between adjacent mentions, so prompts such as “person from @Image 2 with the clothes in @Image 1” assign character and outfit roles to the correct references.

### Changed

- Reference cards now show the role inferred from the prompt after execution and explain that exact visual traits require card descriptions because the deterministic compiler does not inspect pixels.

## [0.1.0-alpha.6] - 2026-08-09

### Added

- Added a readable, tensor-free console execution report with mode, route and reason, target and actual resolution, seed, speed, frames, prompt shaping, reference roles and retention, original prompt, compiled H3 prompt, and diagnostics.
- Added concise model-bundle, selected-transformer, and fully resolved sampling reports, including matched PDD artifact names when that backend is active.

## [0.1.0-alpha.5] - 2026-08-09

### Fixed

- Removed the circular ComfyUI node/panel height calculation that made the Director grow downward on every layout pass, and reset already-serialized runaway heights on load.
- Made an unconfigured standalone VLM analyzer fall back to the built-in H3 production-brief compiler instead of aborting generation.

### Changed

- Replaced the bare megapixel number field with a bounded 0.20–2.00 MP slider, live formatted value, live aligned dimensions, visible limits, and a plain-language native-cap explanation.
- Removed the confusing analyzer filesystem-path control from the Director. H3's selected ConvRot Qwen3-VL remains the final multimodal conditioning encoder; future generative analyzers will use a proper node connection instead of a typed path.

## [0.1.0-alpha.4] - 2026-08-09

### Fixed

- Restored the Easy-derived `@Image` prompt editor after the compact Studio panel accidentally hid both the native prompt widget and its DOM replacement.
- Prevented an absent compiled-result section from rendering as the literal text `null`.
- Made the Director open at a useful full height and let the panel expand or contract with manual node resizing.

### Added

- Added optional Mamad8 PDD REF2VA checkpoint-600 and checkpoint-900 profiles through external-node discovery, deterministic paired-artifact resolution, enforced four-step Euler scheduling, and actionable fail-closed diagnostics.
- Added concise in-node explanations for prompt shaping, reference priority, sampling profiles, route selection, and the separate optional VLM analyzer.

## [0.1.0-alpha.3] - 2026-08-09

### Fixed

- Preserved the backend's exact `Custom` resolution value, eliminating prompt validation failures.
- Hidden Width, Height, seed control, and serialized state plumbing from the product UI.
- Reduced the prompt editor and Director footprint and connected the visible Speed selector to subgraph sampling.
- Replaced sequential full-size upload previews with parallel multi-upload, drag-and-drop, and cached thumbnails.

### Added

- Execution results now reveal the compiled production brief and inferred role/retention label for every `@Image`.
- Added an optional native TAEH3 live-preview node. It affects sampling previews only; the full H3 VAE still produces final images.

## [0.1.0-alpha.2] - 2026-08-09

### Fixed

- Removed all nonexistent `image_1.png`–`image_3.png` workflow placeholders and their blocking required-input errors.
- The bundled workflow now opens with zero references and is immediately runnable for text-to-image.
- Removed the unconsumed Context Inspector and separated the Director from model nodes so node height cannot cover them.

### Added

- Integrated multi-image upload directly inside the Director reference panel through ComfyUI's `/upload/image` endpoint.
- Uploaded files become real ordered `@Image N` cards with thumbnails, roles, retention, descriptions, reordering, and removal.
- Python loads integrated uploads through ComfyUI's canonical `LoadImage` implementation; external image links remain compatible.
- State schema 3 records safe ComfyUI storage names separately from display filenames.
- Upload, storage, empty-workflow, unsafe-path, and no-placeholder regression coverage.

### Changed

- The prompt editor and reference panel now use bounded internal scrolling instead of expanding across neighboring workflow nodes.
- The workflow is arranged as four aligned stages: Director, models/conditioning, sampling/extraction, and output.

## [0.1.0-alpha.1] - 2026-08-09

### Added

- A versioned H3 Studio request schema with migration from the initial settings layout.
- A visible H3 Studio Director with Easy-compatible virtual media links and `@Image` mention chips.
- Nine ordered image cards with thumbnails, role, retention, description, move, and remove controls.
- Deterministic four-section production-brief compilation and friendly-reference validation.
- Optional explicit local Transformers VLM analysis with no silent downloads.
- H3-native aspect-ratio and megapixel planning aligned to 32 with native-area protection.
- Explicit automatic/forced FL2VA and REF2VA routing with diagnostics.
- A lazy dual-transformer loader that keeps only the selected H3 transformer active.
- Combined condition/route preparation without a duplicate Qwen conditioning pass.
- Base and experimental sampling profiles, exact temporal-packet decode, and still-selection strategies.
- A deterministic 2,103-line unified workflow and reusable sampling/decode subgraph.
- Backend, frontend, workflow, node-surface, and release-integrity checks.
- Lightning.ai smoke-test documentation and honest local/GPU verification boundaries.

### Excluded

- H3 Hub and the old monolithic Hub UI.
- App Mode/App Builder integration.
- Model installer, deleter, storage scanner, or Lightning launcher scripts.
- Audio generation and image-prompt soundscape fields.

### Known validation boundary

- CUDA generation and visual-quality comparisons have not been run in the target Lightning.ai workspace from this repository. This prerelease must remain marked alpha until the smoke-test matrix passes there.
