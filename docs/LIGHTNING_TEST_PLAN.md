# Lightning.ai smoke-test plan

This is the minimum real-runtime gate for the private alpha. It intentionally avoids exhaustive visual testing.

## Record first

Capture the ComfyUI commit/version, frontend version, GPU, Python/PyTorch versions, installed H3 Studio commit, and the exact FL2VA, REF2VA, Qwen3-VL, and video VAE filenames.

## Import and UI

Start ComfyUI and confirm there are no H3 Studio import errors. Open the bundled workflow. Confirm it opens at `0/9` with no missing-file errors and the model nodes do not overlap the Director. Click **Add images** inside the Director, upload three real images, confirm all thumbnails appear, then type `@` and insert each image. Save, reload, and confirm order, storage-backed thumbnails, roles, retention, descriptions, aspect, megapixels, seed, and prompt survive.

## Generation matrix

Run only these representative paths:

| Case | References | Mode/route | Expected |
| --- | ---: | --- | --- |
| Clean T2I | 0 | Auto | FL2VA; one saved still; no missing-reference error |
| Anchored I2I | 1 | Image to image / Auto | FL2VA anchor; fitted source reported |
| Reference generation | 3 | Auto | REF2VA; all three `<Picture N>` references present |
| Explicit comparison | 3 | Forced REF2VA | Same route reported; one final still |

For each run, record resolved dimensions, route diagnostic, sampling profile, decoded frame count, selected index, peak VRAM if convenient, and whether Preview/Save received exactly one final image.

## Prompt checks

In Production Brief mode, inspect the compiled prompt and confirm section order, correct image ordinals, exact quoted text, and no audio fields. In VLM mode, use an explicit local instruction model path and verify ComfyUI performs no download. Confirm the enhanced output is materially richer than deterministic role inference before keeping that analyzer configuration.

## Stop conditions

Stop after an import error, an unknown node, a route/model mismatch, a missing `<Picture N>` despite a connected image, a state loss after reload, a duplicate Qwen encode that materially increases cost, or a decode batch that never reaches Single Image Output. Capture the console traceback and workflow JSON before changing code.

Passing Python/JavaScript checks alone is not sufficient to mark these paths verified.
