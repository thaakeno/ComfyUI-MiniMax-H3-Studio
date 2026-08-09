# Changelog

All notable changes are recorded here. The format follows Keep a Changelog; versions use semantic versioning with prerelease identifiers while Lightning GPU validation is incomplete.

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
