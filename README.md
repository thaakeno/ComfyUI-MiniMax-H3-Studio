
# MiniMax H3 Studio

### A reference-aware still-image workspace for MiniMax H3 in ComfyUI.

Build text-to-image, anchored edits, multi-reference compositions, and controlled benchmark matrices from one maintained workflow.

<p>
  <a href="https://github.com/thaakeno/ComfyUI-MiniMax-H3-Studio/stargazers"><img alt="Star H3 Studio" src="https://img.shields.io/badge/%E2%98%85%20Star-H3%20Studio-34D3B5?style=for-the-badge&logo=github&logoColor=white&labelColor=171B1F"></a>
  <img alt="ComfyUI custom nodes" src="https://img.shields.io/badge/ComfyUI-Custom%20Nodes-0EA5E9?style=for-the-badge&labelColor=171B1F">
  <img alt="MiniMax H3 profiles" src="https://img.shields.io/badge/H3-Base%20%C2%B7%20LightX%20%C2%B7%20PDD-A855F7?style=for-the-badge&labelColor=171B1F">
  <img alt="Project status alpha" src="https://img.shields.io/badge/Status-Alpha-F59E0B?style=for-the-badge&labelColor=171B1F">
  <img alt="Images generated" src="https://h3-studio-counter.h3-studio-counter.workers.dev/badge.svg">
</p>

## **Direct the image, understand every reference, and keep the graph readable.**
<img width="3264" height="1408" alt="ComfyUI_temp_krtgv_00010_" src="https://github.com/user-attachments/assets/91b541b9-98a4-4d14-8b6a-5916b02baa9d" />

</div>

> [!IMPORTANT]
> H3 Studio is alpha software built around an evolving audio-video model. Keep working workflow copies when updating ComfyUI, checkpoints, or acceleration nodes. High-resolution generation is experimental; more pixels do not guarantee more learned detail.


<img width="1032" height="478" alt="chrome_Qq5N3IDeDL" src="https://github.com/user-attachments/assets/64b62853-aa77-4932-a57f-5801b503a5e9" />
<img width="1032" height="478" alt="chrome_nKGRTNd8ri" src="https://github.com/user-attachments/assets/b50b4cc1-b8c0-4a7a-85b2-0e16a528edd2" />

> [!NOTE]
> **An official image-specific H3 descendant is planned.** In the MiniMax H3 team AMA, H3 researcher Kiro Song said the team is deriving a dedicated image model from a common ancestor in the H3 lineage. It is expected to reuse H3's VAE encoder through weight slicing and receive a dedicated image-generation VAE decoder. MiniMax did not announce a release date or measured quality improvement, so H3 Studio's current still-image and experimental T=1 paths remain community solutions for now. [Read the team response.](https://www.reddit.com/r/StableDiffusion/comments/1vh9rtw/comment/p23ecga/)

## One Studio, three generation paths

| Path | What it does | H3 route |
| --- | --- | --- |
| Text to image | Generates from the prompt without secretly consuming uploaded images | FL2VA |
| Anchored image edit | Uses Image 1 as the first-frame/source canvas | FL2VA |
| Reference mix/edit | Regenerates from ordered references with explicit ownership | REF2VA |

<img width="1600" height="1000" alt="H3StudioComparison_temp_rlcer_00005_" src="https://github.com/user-attachments/assets/9e68b1dc-e7d1-4a4e-8c1c-d4379fa081c5" />


Auto selects the valid route from your requested mode and enabled references. Impossible PDD, LightX/REF2VA, forced-route, and missing-reference combinations are rejected before expensive model work starts.

## What you get

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>🎯 Direct references precisely</h3>
      Upload up to nine images, inspect them at full size, and address them as <code>@Image1</code>–<code>@Image9</code>. Each card preserves its role, retention policy, dimensions, fingerprint, description, and thumbnail across workflow reloads.
    </td>
    <td width="50%" valign="top">
      <h3>🧠 Analyze once, reuse the facts</h3>
      Optional Qwen3-VL pixel analysis produces factual source records. A separate cached text-only Qwen pass enhances the prompt. The default reuses the same 4B checkpoint; 4B, 8B, and mixed analyzer/writer choices remain available.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>⚡ Choose a real sampling recipe</h3>
      Compare native Base RES20/RES12, the official LightX v1.0 FL2V 8-step ComfyUI adapter, legacy Kijai LightX v0.1 four-step profiles, or Mamad8's external four-step PDD REF2VA students. Profile metadata keeps those adapter families separate instead of silently mixing recipes.
    </td>
    <td width="50%" valign="top">
      <h3>🔬 Benchmark more than A/B</h3>
      Build guarded profile × resolution × repeat matrices. See the exact run count before queueing, live progress and honest ETA, optional cell previews, references, original prompt, seeds, timings, and real output dimensions.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🧩 Stack your own H3 LoRAs</h3>
      Add up to six installed style, character, detail, or other MiniMax H3-compatible LoRAs directly in the Director. Each row has its own enable switch, strength, order, and persisted workflow state. Current ComfyUI uses additive bypass-forward injection instead of merging and requantizing the H3 base weights.
    </td>
    <td width="50%" valign="top">
      <h3>🚀 Stage the expensive model once</h3>
      On cache misses Studio gives the 32B text encoder the GPU for its encode, releases it, then fully materializes the final patched diffusion model before sampling and the VAE before tiled decode. This targets the repeated DynamicVRAM streaming that can otherwise dominate H3 on 20–24 GB GPUs.
    </td>
  </tr>
</table>

# Image examples generated by H3
<img width="3264" height="1408" alt="ComfyUI_temp_krtgv_00011_" src="https://github.com/user-attachments/assets/160a2623-34a2-48ea-9d4b-1b3fc9699970" />
<img width="1920" height="1088" alt="ComfyUI_temp_cbyme_00013_" src="https://github.com/user-attachments/assets/8054886b-49b9-4642-a97e-59c59a2fcf02" />
<img width="1920" height="1088" alt="ComfyUI_temp_cbyme_00014_" src="https://github.com/user-attachments/assets/c1e28ee6-9587-4117-8f10-012e45e8c41d" />
<img width="3264" height="1824" alt="ComfyUI_temp_cbyme_00007_" src="https://github.com/user-attachments/assets/1a2133f0-a95d-4680-9baf-4dc64575f5e6" />
<img width="1888" height="1056" alt="ComfyUI_temp_svkjp_00001_" src="https://github.com/user-attachments/assets/d023316b-c141-4b8b-b6b5-5d52822c6295" />
<img width="3264" height="1408" alt="ComfyUI_temp_krtgv_00013_" src="https://github.com/user-attachments/assets/fb332f8c-619e-4a97-bf94-ac7d1e9eb307" />
<img width="1600" height="1000" alt="H3StudioComparison_temp_acpja_00002_" src="https://github.com/user-attachments/assets/b080a12a-4abb-41a8-93b5-7a0b90fb4ded" />





## Quick start

1. Open [`example_workflows/H3_Studio_Unified_Image.json`](example_workflows/H3_Studio_Unified_Image.json) in ComfyUI.
2. Select the installed FL2VA, REF2VA, 32B H3 text encoder, and video VAE in **H3 models · lazy route loader**.
3. Write a prompt in the **Image Director**. Add references only when the image actually needs them.
4. Assign each reference a narrow role and say what belongs to it: `Keep the identity and pose from @Image1; transfer only the jacket from @Image2.`
5. Optionally open **Custom LoRAs** in the Director, add installed H3-compatible LoRAs, set each strength, and arrange the stack order.
6. Choose a sampling profile, resolution mode, frame profile, and seed behavior, then queue.



## Install

From your ComfyUI installation:

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/thaakeno/ComfyUI-MiniMax-H3-Studio.git
cd ComfyUI-MiniMax-H3-Studio
python -m pip install -r requirements.txt
git log -1 --format='Installed H3 Studio %h · %s'
```

Restart ComfyUI, hard-refresh the frontend, and open the maintained workflow. H3 Studio does not download models automatically.

For a reproducible shared install, pin the current release instead of following later development commits:

```bash
cd /path/to/ComfyUI/custom_nodes
git clone --branch v0.1.0-alpha.13 --depth 1 https://github.com/thaakeno/ComfyUI-MiniMax-H3-Studio.git
cd ComfyUI-MiniMax-H3-Studio
python -m pip install -r requirements.txt
```

To update an existing Git clone:

```bash
cd /path/to/ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Studio
git pull --ff-only
git log -1 --format='Updated H3 Studio %h · %s'
```

## Models

| Component | ComfyUI folder | Source |
| --- | --- | --- |
| Proven pruned W4A8 FL2VA and REF2VA defaults | `models/diffusion_models/` | [Kijai/MiniMax-H3-experimental](https://huggingface.co/Kijai/MiniMax-H3-experimental) |
| MiniMax H3 32B conditioning encoder | `models/text_encoders/` | [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) |
| H3 video VAE | `models/vae/` | [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) |
| Qwen3-VL 4B/8B analyzer and prompt writer, optional | `models/text_encoders/` | [Comfy-Org/Qwen3-VL](https://huggingface.co/Comfy-Org/Qwen3-VL) |
| LightX v1.0 FL2V 8-step ComfyUI LoRA, optional | `models/loras/` | [lightx2v/Minimax-h3-Turbo](https://huggingface.co/lightx2v/Minimax-h3-Turbo/blob/main/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors) |
| LightX v0.1 resized rank-21 LoRA, legacy optional | `models/loras/` | [Kijai/MiniMax-H3_comfy](https://huggingface.co/Kijai/MiniMax-H3_comfy) |
| Your H3-compatible style/character/detail LoRAs, optional | `models/loras/` | Any MiniMax H3-compatible LoRA; select it from the Director |
| TAEH3 approximate preview, optional | `models/vae_approx/` | [Kijai/MiniMax-H3-TAE](https://huggingface.co/Kijai/MiniMax-H3-TAE) |
| PDD LoRA + heads, optional | `models/loras/`, `models/pdd_heads/` | [Mamad8 PDD](https://huggingface.co/Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8) |
| T=1 Image VAE, experimental | `models/vae/` | [Mamad8 Image VAE](https://huggingface.co/Mamad8/MiniMax-H3-Image-VAE) |

PDD also requires the separately installed [ComfyUI-MiniMaxH3-PDD-Mamad8](https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8) package. H3 Studio integrates its registered execution surface; it does not copy or bundle that GPL implementation.

## Profiles and acceleration

| Profile | Recipe | Intended use |
| --- | --- | --- |
| Base Quality | RES, 20 steps | Safest native quality baseline |
| Base Balanced | RES, 12 steps | Faster native comparison |
| LightX v1.0 FL2V 8-step | Official ComfyUI BF16 adapter at `1.0`; Euler/simple, 8 steps, H3 DMD-family shifts `6/3` | Fast T2I or single-source FL2VA work |
| LightX v0.1 ER-SDE | Resized rank-21 adapter at `0.75`, 4 steps | Legacy empirical Kijai recipe |
| LightX v0.1 SA-Solver | Resized rank-21 adapter at `0.75`, 4 steps | Legacy alternate empirical recipe |
| PDD 600 / 900 | Matching REF2VA student LoRA + heads, 4 steps | Optional accelerated reference work |

LightX2V also announced an official **v1.0 4-step 768p distilled LoRA** with guidance-free inference, `video_flow_shift=6`, `audio_flow_shift=3`, and LoRA alpha 128. H3 Studio currently auto-resolves only the verified `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` ComfyUI artifact; the older v0.1 profiles remain available for reproducibility. All configured LightX adapters are FL2V/FL2VA-only, so Studio rejects them before model work when a request resolves to REF2VA.

### Custom LoRA stack

The Director can stack up to six model LoRAs from `models/loras/`. Each entry has its own enabled state, strength from `-4.0` to `4.0`, and order. The entire stack persists in Studio state and survives workflow reloads. H3 Studio rejects duplicate active acceleration artifacts so a LightX/PDD LoRA cannot accidentally be applied twice.

On current ComfyUI, built-in LightX and user LoRAs use bypass-forward injection. This keeps adapter math separate from the W4A8/INT8/FP8 base and avoids the expensive merge → requantize path. Studio explicitly combines ComfyUI's bypass injection lists when several adapters are active, so a later style LoRA cannot silently replace the LightX adapter. LoRAs still need to target MiniMax H3; an SDXL/Flux/Wan LoRA is not made compatible merely by appearing in the picker.

### Fast stage residency

H3 Studio keeps the existing independent prompt, reference-VAE, source-VAE and latent caches, then optimizes the expensive cache-miss boundaries instead of fighting ComfyUI globally:

- The 32B H3 text encoder is fully materialized only for a real text-conditioning cache miss, encoded once, cached, and targeted for release before the diffusion stage.
- LightX/PDD and custom-LoRA patch graphs are cached. After all adapters are active, Studio asks ComfyUI to fully materialize the final patched H3 transformer before KSampler begins.
- Before final H3 decode, Studio fully materializes the selected VAE so its internally tiled decoder does not repeatedly stream the same weights tile-by-tile.
- Every full-residency request is nonfatal. If the complete stage cannot fit, Studio falls back to ComfyUI's DynamicVRAM path rather than changing the generation contract.

This is intentionally stage-scoped rather than a global `--highvram` switch. Logs report the residency mode and load time for the text encoder, diffusion model, and VAE so cold/warm behavior is visible.

> [!WARNING]
> `/dev/shm` is RAM, not free disk cache. On low-RAM cloud instances, putting large H3 safetensors in `/dev/shm` can consume the same host memory ComfyUI needs for staged weights and make loading dramatically slower. H3 Studio warns when the selected model paths create obvious tmpfs pressure; prefer persistent disk-backed model paths when host RAM is tight.

## Direct resolution

The Director offers two explicit planning modes:

- **Conservative:** keeps the older approximately 1 MP working area for predictable memory use.
- **Direct:** sends the aligned target canvas to H3 from 0.2 MP through approximately 8.5 MP.

The slider labels draft, recommended, extended, experimental, and extreme ranges and always shows the real aligned dimensions. Direct 2/4/8 MP generation is available for experimentation, but H3 Base is not a dedicated super-resolution model. Very large canvases can raise attention cost, decode time, RAM, VRAM, and failure risk without proportional detail gains.

## Decode choices

The Director exposes the decoder separately from sampling speed:

- **Original H3 Video VAE:** the quality/default path. Choose 5, 9, 13, or 20 temporal frames; more candidates increase sampling and decoding work.
- **T=1 Image VAE:** the fastest decode path. It samples and decodes one still latent through Mamad8's optional experimental image VAE, but may soften typography, hair, fine contours, and microtexture.

Current ComfyUI's MiniMax H3 video VAE uses a 36-layer ViT3D decoder, output-identical temporal chunking, and internal spatial tiling. Chunking mainly reduces peak memory; it does not by itself make decode fast. H3 Studio now fully stages the selected VAE immediately before the unchanged decoder path so DynamicVRAM does not have to stream the same decoder weights again for every spatial tile. It does not change H3's tile geometry, temporal attention, selected frames, or decoded pixels. The actual VAE load and decode durations are logged separately, and insufficient VRAM falls back to normal ComfyUI behavior.

## Benchmark Lab

Benchmark Lab is a guarded matrix, not a hard-coded A/B node. Two profiles still make a simple comparison; additional Base, LightX, or PDD profiles expand it. Resolution targets and repeats form the other axes.

Before execution, the node reports the exact number of generations and blocks oversized matrices unless you explicitly allow them. During execution it reports the active cell, completed and remaining counts, profile, aligned resolution, elapsed time, and an ETA only after enough completed cells exist to support one. Live cell previews are optional and can be disabled for maximum throughput.

The final comparison sheet can include a separate reference strip with correct `@ImageN` labels, the original prompt, and only useful cell metadata: profile, seed, requested/real dimensions, repeat, and sampling time.

## Prompt and reference behavior

H3 Studio keeps three things separate:

1. **Factual pixel analysis** describes visible reference content and is cached by image fingerprint.
2. **Reference ownership** assigns identity, character, style, composition, pose, outfit, object, environment, and other narrow responsibilities.
3. **Generative prompt direction** uses the selected Qwen3-VL writer to create a compact production instruction. `Same as image analyzer` reuses one checkpoint; selecting another 4B/8B file intentionally stages two.
4. **Prompt compilation** converts friendly `@ImageN` mentions into H3's model-facing `<Picture N>` form deterministically.

The maintained workflow uses Auto Qwen3-VL 4B for analysis and `Same as image analyzer` for writing. Writer output is capped to a compact 120–220-word target instead of the former 900-token ceiling, validated for reference assignments and hard visible constraints, and cached independently from factual image analysis.

Malformed or truncated analyzer JSON is repaired/retried and useful fallback text is preserved. Legacy mention forms such as `@Image 1` remain accepted, but saved state is canonicalized to `@Image1`.

Reference editing is semantic regeneration, not pixel-locked compositing or mask inpainting. Explicit ownership and retention language improves control; it cannot guarantee exact geometry.

## Validation and support

Local checks cover Python and frontend syntax, deterministic compilation, state migration, workflow regeneration/schema, node registration, route validation, PNG metadata restoration, performance-residency contracts, custom-LoRA stack behavior, and artifact consistency. CUDA speed, peak memory, model availability, and visual quality still require a real GPU run with the exact installed ComfyUI build.

If generation fails, open an [issue](https://github.com/thaakeno/ComfyUI-MiniMax-H3-Studio/issues) with the full traceback, ComfyUI version, GPU/VRAM, selected model filenames, route, profile, resolution, and a workflow JSON or metadata PNG when safe.

<details>
<summary><strong>Development checks</strong></summary>

```bash
uv sync --extra dev
uv run ruff check h3studio tests tools
uv run pytest -q
npm run check
uv run python tools/generate_workflows.py --check
uv run python tools/validate_workflows.py
uv run python tools/audit_nodes.py
uv run python tools/release_check.py
```

</details>

## Credits and project boundaries

H3 Studio adapts the ordered media interaction and mention-editor foundations from [ComfyUI-MiniMaxH3-Easy](https://github.com/nkxx188/ComfyUI-MiniMaxH3-Easy) under MIT, and resolution/decode/workflow foundations from [ComfyUI-MiniMax-H3-Image-Studio](https://github.com/astropuzzo/ComfyUI-MiniMax-H3-Image-Studio) under the Unlicense.

Kijai, LightX2V, and Mamad8 model artifacts and optional nodes remain external works under their published terms. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for the exact boundaries. This independent project is not endorsed by MiniMax, ComfyUI, or the referenced projects.

## Star history

If H3 Studio makes MiniMax H3 easier to direct, a star is the clearest signal to keep developing it.

<div align="center">
  <a href="https://www.star-history.com/#thaakeno/ComfyUI-MiniMax-H3-Studio&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=thaakeno/ComfyUI-MiniMax-H3-Studio&type=Date&theme=dark">
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=thaakeno/ComfyUI-MiniMax-H3-Studio&type=Date">
      <img alt="MiniMax H3 Studio star history" src="https://api.star-history.com/svg?repos=thaakeno/ComfyUI-MiniMax-H3-Studio&type=Date" width="720">
    </picture>
  </a>
</div>

> [!NOTE]
> **What the GENERATED badge counts:** successful images saved through H3 Studio. It sends only a batched number—never prompts, images, references, seeds, hardware details, paths, or identifiers. Set `H3STUDIO_TELEMETRY=0` to opt out; [implementation details](telemetry/README.md) are public.

## License

Original H3 Studio code is available under the [MIT License](LICENSE). Adapted files retain their upstream notices and terms; external models and optional custom nodes retain their own licenses.