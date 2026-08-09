# ComfyUI MiniMax H3 Studio

MiniMax H3 Studio turns H3 into a focused still-image and reference-editing workspace for ComfyUI. It combines an Easy-style `@Image` editor, pixel-aware prompt direction, FL2VA/REF2VA routing, exact temporal decoding, Base/LightX/PDD sampling, live TAEH3 previews, and controlled A/B tests in one maintained workflow.

> Alpha software. Local tests cover code, state migration, prompt compilation, workflow structure, and node registration. Production H3 generation still depends on the user's ComfyUI build, CUDA stack, and model files.

## Why this exists

H3 is an audio-video model, but short temporal packets can produce unusually capable still images and edits. The hard part is not merely saving frame zero: it is assigning multiple references correctly, producing a prompt H3 can follow, choosing FL2VA or REF2VA, applying each accelerator's real recipe, and extracting a stable final still without turning the graph into a maze.

H3 Studio provides:

- Integrated multi-upload and drag-and-drop for up to nine ordered references.
- Rich `@Image1`–`@Image9` mentions, thumbnails, reordering, roles, and retention controls.
- Text-to-image, anchored image-to-image, and multi-reference REF2VA editing.
- Qwen3-VL pixel analysis with cached factual descriptions; H3 always receives the untouched originals.
- An optional cached text-only writer pass that expands the request into a validated 200–450 word production direction.
- Deterministic one-line and four-section prompt formats.
- Base RES20/RES12, real LightX v0.1 ER-SDE/SA-Solver, and optional external Mamad8 PDD profiles.
- Exact H3 packet decoding, stable-frame selection, optional TAEH3 sampling previews, and click-to-expand output previews.
- A lazy Benchmark Lab for Base-vs-LoRA, LoRA-vs-LoRA, resolution tests, seed sweeps, and same-latent VAE comparisons.

H3 Hub, audio controls, fake sound fields, and App Mode are intentionally outside this project.

## Workflow

Open [H3_Studio_Unified_Image.json](example_workflows/H3_Studio_Unified_Image.json). It starts with zero placeholder images and can immediately run text-to-image.

Write naturally:

```text
Show the man from @Image1 holding the fluffy version of @Image2 in both hands.
```

When cards remain auto-managed, prompt grammar repairs generic analyzer assignments: a person/character source becomes `character + fully_preserved`; a prop, glasses, clothing, or style donor becomes the narrower role with `attribute_transfer`. Manual card choices remain authoritative.

`Analyze image pixels` performs factual visual inspection. `Detailed prompt expansion` is a separate text-only pass. Turning the second pass off intentionally keeps the generated instruction short; the maintained workflow ships with it on.

The final H3 prompt uses native `<Picture N>` references internally because that is the model-facing syntax. The Studio UI continues to show friendly `@ImageN` tags.

## Generation paths

| Mode | Model path | Meaning |
| --- | --- | --- |
| Text to image | FL2VA | New image from text; references are ignored deliberately |
| Image to image | FL2VA | Image 1 is a first-frame/source anchor |
| Reference mix/edit | REF2VA | Independent ordered references are synthesized by role |
| Auto | FL2VA/REF2VA | No image → T2I; one image → anchor; multiple images → REF2VA |

Reference editing is semantic regeneration, not pixel-locked compositing. `fully_preserved` requests strong identity/source retention; `attribute_transfer` transfers only the assigned trait; `partially_preserved` permits broader adaptation; `reference_only` supplies context without asking H3 to reproduce it.

## Models

| Component | Folder | Source |
| --- | --- | --- |
| FL2VA, REF2VA, H3 32B conditioning encoder, video VAE | `models/diffusion_models`, `text_encoders`, `vae` | [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) |
| Full Qwen3-VL 4B/8B analyzer and writer | `models/text_encoders` | [Comfy-Org/Qwen3-VL](https://huggingface.co/Comfy-Org/Qwen3-VL) |
| LightX v0.1 LoRA | `models/loras` | [Kijai/MiniMax-H3_comfy](https://huggingface.co/Kijai/MiniMax-H3_comfy) |
| TAEH3 approximate preview decoder | `models/vae_approx` | [Kijai/MiniMax-H3-TAE](https://huggingface.co/Kijai/MiniMax-H3-TAE) |
| PDD LoRA and heads | `models/loras`, `models/pdd_heads` | [Mamad8 PDD](https://huggingface.co/Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8) |
| Experimental T=1 Image VAE | `models/vae` | [Mamad8 Image VAE](https://huggingface.co/Mamad8/MiniMax-H3-Image-VAE) |

The H3-specific 32B ConvRot file is the multimodal conditioning encoder selected with ComfyUI's MiniMax CLIP loader. H3 Studio does not assume that a particular conditioning checkpoint exposes a general chat-generation head. Prompt writing therefore uses a full Qwen3-VL checkpoint; no LM Studio or Ollama service is involved.

The 4B model is sufficient for factual source records. The optional 8B FP8 checkpoint is recommended for richer instruction writing. Analyzer copies default to a 512 px maximum edge, with 384, 768, and native-resolution choices; original reference tensors are never resized before H3.

## Install or update on Lightning.ai

Minimal node update:

```bash
H3_ROOT="$HOME/ComfyUI"
STUDIO="$H3_ROOT/custom_nodes/ComfyUI-MiniMax-H3-Studio"

if [ -d "$STUDIO/.git" ]; then
  git -C "$STUDIO" pull --ff-only
else
  git clone https://github.com/thaakeno/ComfyUI-MiniMax-H3-Studio.git "$STUDIO"
fi

python -m pip install -r "$STUDIO/requirements.txt"
git -C "$STUDIO" log -1 --format='H3 Studio %h · %s'
python - <<'PY'
from pathlib import Path
import tomllib
p = Path.home() / "ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Studio/pyproject.toml"
print("Version:", tomllib.loads(p.read_text(encoding="utf-8"))["project"]["version"])
PY
```

Restart ComfyUI, refresh the browser, and reopen the bundled workflow. Models are never downloaded at import or queue time.

### Optional complete model/backend install

This installs the full Qwen3-VL 8B FP8 writer, LightX, TAEH3, PDD 600/900, the external GPL PDD node, and the experimental Image VAE using `hf download`. It does not redownload files whose local metadata already matches.

```bash
H3_ROOT="$HOME/ComfyUI"
python -m pip install -U huggingface_hub

PDD_NODE="$H3_ROOT/custom_nodes/ComfyUI-MiniMaxH3-PDD-Mamad8"
if [ -d "$PDD_NODE/.git" ]; then
  git -C "$PDD_NODE" pull --ff-only
else
  git clone https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8.git "$PDD_NODE"
fi

hf download Comfy-Org/Qwen3-VL text_encoders/qwen3vl_8b_fp8_scaled.safetensors \
  --local-dir "$H3_ROOT/models"
hf download Kijai/MiniMax-H3_comfy loras/minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy.safetensors \
  --local-dir "$H3_ROOT/models"
hf download Kijai/MiniMax-H3-TAE vae_approx/taeh3.safetensors \
  --local-dir "$H3_ROOT/models"
hf download Mamad8/MiniMax-H3-Image-VAE minimax_h3_t1_image_vae_step1597.safetensors \
  --local-dir "$H3_ROOT/models/vae"
hf download Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8 \
  LORA_h3_pdd_af384_step600_s.safetensors LORA_h3_pdd_af384_step900_s.safetensors \
  --local-dir "$H3_ROOT/models/loras"
hf download Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8 \
  HEADS_h3_pdd_af384_step600_bank.safetensors HEADS_h3_pdd_af384_step900_bank.safetensors \
  --local-dir "$H3_ROOT/models/pdd_heads"

test -s "$H3_ROOT/models/text_encoders/qwen3vl_8b_fp8_scaled.safetensors" && echo "✓ Qwen3-VL 8B"
test -s "$H3_ROOT/models/vae/minimax_h3_t1_image_vae_step1597.safetensors" && echo "✓ H3 Image VAE"
test -d "$PDD_NODE" && echo "✓ Mamad8 PDD node"
```

## Acceleration

LightX ER-SDE and SA-Solver are different four-step stochastic recipes; neither is universally better. H3 Studio loads the actual LightX v0.1 LoRA rather than merely reducing steps.

PDD is REF2VA-only and requires the separately installed Mamad8 node plus the matching LoRA/heads pair. H3 Studio calls its registered node surface but copies none of its GPL implementation. Current ComfyUI can use bypass-forward adapters to avoid slow quantized merge/requantize work.

## Benchmark Lab

Set the purple `Run mode` switch to Benchmark. ComfyUI's lazy evaluation then requests only the benchmark branch; the normal sampler is not executed, eliminating the old seventh generation.

Sampling mode compares any Profile A and Profile B at 0.40, 1.00, and 2.00 MP. This supports Base-vs-LoRA and LoRA-vs-LoRA. Same seed is the fair default. New seed each row keeps pairs comparable. New seed every image is explicitly a diversity sweep and cannot isolate profile or resolution quality.

The matrix groups execution by profile to reduce patch swapping and reuses variants whose requested 1 MP/2 MP targets collapse to the same native-capped canvas, seed, and prompt. Each cell reports requested/actual size, seed, profile, and CUDA-synchronized sampler time.

VAE mode samples one `T=1` latent once, then decodes those identical bytes through the original H3 video VAE and Mamad8's experimental Image VAE. This isolates decoder differences. The Image VAE is image-only and remains disabled by default; it must not replace the video VAE in multi-frame workflows.

## Upscaling, outpainting, and inpainting

For deterministic upscaling, connect ComfyUI's built-in `UpscaleModelLoader` and `ImageUpscaleWithModel` after H3 Studio's selected still. This keeps H3 reference synthesis separate from the restoration model.

Semantic outpainting already works by expanding the target aspect ratio and explicitly locating the original image inside the new frame. Exact masked inpainting is not advertised: H3 Studio currently has no verified mask-conditioned H3 route. ComfyUI's `VAE Encode (for Inpainting)` is useful with models trained for that contract, but semantic REF2VA editing is not equivalent to pixel-locked masked inpainting.

## Development and verification

```bash
uv sync --extra dev
uv run ruff check h3studio tests tools
uv run pytest -q
npm run check
python tools/generate_workflows.py --check
python tools/validate_workflows.py
python tools/audit_nodes.py
python tools/release_check.py
```

These checks cannot prove CUDA generation. Use [LIGHTNING_TEST_PLAN.md](docs/LIGHTNING_TEST_PLAN.md) for the short real-environment smoke test.

The workflow JSON and reusable sampling subgraph are generated by [generate_workflows.py](tools/generate_workflows.py). Architecture, node, and prompt details live in [docs/](docs/).

## Inspiration and credit

H3 Studio openly builds on ideas and permitted code from:

- [nkxx188/ComfyUI-MiniMaxH3-Easy](https://github.com/nkxx188/ComfyUI-MiniMaxH3-Easy): the excellent ordered `@Image` interaction and virtual media-link approach (MIT).
- [astropuzzo/ComfyUI-MiniMax-H3-Image-Studio](https://github.com/astropuzzo/ComfyUI-MiniMax-H3-Image-Studio): resolution, sampling, temporal decode, and still-selection foundations (Unlicense).
- [mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8](https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8): optional external PDD execution and research checkpoints (GPL package, not copied).
- Alier's private Unified Image Director and v1.3.7 workflow: role-aware direction, routing experiments, and the visual workflow hierarchy.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This independent project is not endorsed by MiniMax, ComfyUI, or the inspiration projects.

## License

Original project code is [MIT licensed](LICENSE). Adapted files retain their upstream notices and terms. MIT is intentionally used for the original code because it is simple, permissive, Registry-friendly, and compatible with the included MIT/Unlicense adaptations. External GPL nodes remain separate dependencies.
