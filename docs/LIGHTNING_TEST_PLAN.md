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

For the optional Benchmark Lab smoke test, keep its fair same-seed default, select any Profile A and Profile B, turn Benchmark ON in the purple lazy switch, and queue once. Confirm the output contains six labeled cells in three resolution rows, every cell shows its seed, `1.00 MP` and `2.00 MP` disclose or reuse identical native-capped variants, every successful cell reports sampling-only seconds, and the normal Preview/Save branch does not produce a seventh image. Then compare LightX against PDD directly. The first cell may include lazy model initialization, so compare warm-cache timings with that caveat. Turn Benchmark OFF again after the test.

If the optional Image VAE is installed, select it in the Loader, choose `VAE decode - same T=1 latent`, and run Benchmark once. Confirm exactly one sampling pass occurs and both labeled cells report the same seed/canvas with separate decode times. Restore `Disabled - original H3 video VAE only` afterward; never use the experimental decoder for a multi-frame profile.

If Mamad8 PDD is installed, run one additional three-reference comparison with `PDD REF2VA · 4-step · ckpt 900`. Confirm the console reports the matched step-900 LoRA and heads filenames, Euler, `trained_blocks`, four steps, strengths `2.0/1.0`, shifts `12/3`, and `contract=enforce`. Then temporarily rename neither file: instead select checkpoint 600 without its files and confirm H3 Studio fails with an actionable missing-artifact message rather than falling back.

## Prompt checks

In Production Brief mode, inspect the compiled prompt and confirm section order, correct image ordinals, exact quoted text, and no audio fields. With image analysis and Detailed prompt expansion enabled, verify the console shows one vision stage followed by one text-only writer stage, the enhanced instruction is detailed and at least 180 words, named styles include concrete rendering traits, and a seed-only rerun reports cache hits for both stages. For `Show the man from @Image1 holding the fluffy version of @Image2 in both hands`, confirm the auto cards visibly change to `character + fully_preserved` and `object + attribute_transfer`, and the generated direction explicitly requires hands/fingers supporting the object's weight with physical contact. Verify ComfyUI performs no download.

## Stop conditions

Stop after an import error, an unknown node, a route/model mismatch, a missing `<Picture N>` despite a connected image, a state loss after reload, a duplicate Qwen encode that materially increases cost, or a decode batch that never reaches Single Image Output. Capture the console traceback and workflow JSON before changing code.

Passing Python/JavaScript checks alone is not sufficient to mark these paths verified.
