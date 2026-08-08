# Changelog

All notable changes are recorded here. The format follows Keep a Changelog; versions use semantic versioning with prerelease identifiers while Lightning GPU validation is incomplete.

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
