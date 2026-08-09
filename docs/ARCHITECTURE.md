# Architecture

## Product boundary

H3 Studio owns still-image direction, reference metadata, prompt compilation, H3 conditioning preparation, route selection, sampling recipes, temporal-packet decode, still selection, and workflow templates. It does not own model acquisition, H3 Hub, Lightning process management, cloud storage, App Mode, video delivery, or audio delivery.

## Data flow

```text
user prompt + ordered image links + role metadata
                    |
              H3 Studio state v8
                    |
        deterministic compiler or optional VLM
                    |
  four-section brief + actual image tensors + route intent
                    |
          Qwen3-VL MiniMax conditioning (once)
                    |
        FL2VA or REF2VA transformer + H3 latent
                    |
          sampler -> exact decode -> still selector
```

The `H3StudioContext` is the boundary between direction and generation. It contains normalized state, compiled prompt, dimensions, selected route, ordered image tensors, filenames, and diagnostics. The condition node consumes it together with a lazy model bundle.

## Frontend boundary

`web/h3studio_ui.js` is an attributed adaptation of Easy's mature virtual media-link and mention editor. New Studio behavior lives under `web/js/`:

- `core/state.js` normalizes, migrates, serializes, and plans resolution.
- `core/dom.js` creates accessible controls without a framework dependency.
- `core/theme.js` owns semantic theme integration and compact tool styling.
- `studio_extension.js` binds the panel to `H3StudioDirector` and mirrors state into compatibility widgets.

The graph-to-prompt hook merges integrated uploads and optional virtual media links into one ordered reference plan. Linked nodes become `media_N` tensor connections; integrated uploads become safe `media_filename_N` values loaded through ComfyUI's canonical image loader. Video and audio are rejected; the capacity is nine images in every mode.

## Backend boundary

- `state.py` defines persistent data.
- `references.py` parses and resolves friendly mentions.
- `resolution.py` performs deterministic dimensions.
- `routing.py` makes route selection explicit.
- `prompting/` owns four-section production briefs and VLM adapters.
- `loader.py` loads shared encoder/VAE objects, optional full analyzer/writer checkpoints, optional T=1 Image VAE, and lazily switches transformer models.
- `director.py` exposes the normal ComfyUI path.
- `acceleration.py` is the MIT interoperability boundary for optional external backends. It contains no Mamad8 PDD implementation; it discovers and invokes the separately installed registered nodes.
- `image_runtime.py` contains attributed resolution, prepare, sampling, decode, and selection foundations adapted from Image Studio.
- `benchmark.py` plans fair profile/resolution matrices, direct LoRA comparisons, and identical-latent decoder tests.
- `nodes/benchmark.py` executes those plans and exposes the lazy branch switch that prevents normal and benchmark sampling from running together.

## Why the Director remains top-level

ComfyUI subgraphs reliably carry typed sockets and ordinary widgets. They do not reliably promote custom DOM controls such as a contenteditable mention editor or image-card collection. Hiding the Director inside a subgraph recreates the exact failure where the prompt becomes a plain box and seed/reference controls disappear.

The bundled workflow therefore subgraphs only sampling and exact-still extraction. This is the maintainable boundary: the custom product surface is visible; repetitive plumbing is collapsed.

## Compatibility strategy

The Director preserves the first twelve legacy Easy widget positions so the adapted editor can migrate known workflows. The complete Studio state is also stored in a versioned JSON widget. Individual role and filename widgets are mirrored for queue compatibility and inspectability.

Frontend hooks are isolated, and every serialized change requires a migration plus JS/Python round-trip tests. Runtime imports stay lazy where possible so pure logic can be tested without ComfyUI.
