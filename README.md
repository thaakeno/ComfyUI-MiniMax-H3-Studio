<div align="center">

# MiniMax H3 Studio

### A reference-aware still-image workspace for MiniMax H3 in ComfyUI.

Build text-to-image, anchored edits, multi-reference compositions, and controlled benchmark matrices from one maintained workflow.

<p>
  <a href="https://github.com/thaakeno/ComfyUI-MiniMax-H3-Studio/stargazers"><img alt="Star H3 Studio" src="https://img.shields.io/badge/%E2%98%85%20Star-H3%20Studio-34D3B5?style=for-the-badge&logo=github&logoColor=white&labelColor=171B1F"></a>
  <img alt="ComfyUI custom nodes" src="https://img.shields.io/badge/ComfyUI-Custom%20Nodes-0EA5E9?style=for-the-badge&labelColor=171B1F">
  <img alt="MiniMax H3 profiles" src="https://img.shields.io/badge/H3-Base%20%C2%B7%20LightX%20%C2%B7%20PDD-A855F7?style=for-the-badge&labelColor=171B1F">
  <img alt="Project status alpha" src="https://img.shields.io/badge/Status-Alpha-F59E0B?style=for-the-badge&labelColor=171B1F">
  <img alt="Images generated" src="https://h3-studio-counter.h3-studio-counter.workers.dev/badge.svg">
  <a href="#license"><img alt="MIT license" src="https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge&labelColor=171B1F"></a>
</p>

**Direct the image, understand every reference, and keep the graph readable.**

</div>

> [!IMPORTANT]
> H3 Studio is alpha software built around an evolving audio-video model. Keep working workflow copies when updating ComfyUI, checkpoints, or acceleration nodes. High-resolution generation is experimental; more pixels do not guarantee more learned detail.

> [!NOTE]
> **An official image-specific H3 descendant is planned.** In the MiniMax H3 team AMA, H3 researcher Kiro Song said the team is deriving a dedicated image model from a common ancestor in the H3 lineage. It is expected to reuse H3's VAE encoder through weight slicing and receive a dedicated image-generation VAE decoder. MiniMax did not announce a release date or measured quality improvement, so H3 Studio's current still-image and experimental T=1 paths remain community solutions for now. [Read the team response.](https://www.reddit.com/r/StableDiffusion/comments/1vh9rtw/comment/p23ecga/)

## One Studio, three generation paths

| Path | What it does | H3 route |
| --- | --- | --- |
| Text to image | Generates from the prompt without secretly consuming uploaded images | FL2VA |
| Anchored image edit | Uses Image 1 as the first-frame/source canvas | FL2VA |
| Reference mix/edit | Regenerates from ordered references with explicit ownership | REF2VA |

Auto selects the valid route from your requested mode and enabled references. Impossible PDD, REF2VA, forced-route, and missing-reference combinations are rejected before expensive model work starts.

## What makes it a Studio

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
      Compare native Base RES20/RES12, Kijai's empirical LightX v0.1 four-step profiles, or Mamad8's external four-step PDD REF2VA students. Profile metadata states what is proven and what remains empirical.
    </td>
    <td width="50%" valign="top">
      <h3>🔬 Benchmark more than A/B</h3>
      Build guarded profile × resolution × repeat matrices. See the exact run count before queueing, live progress and honest ETA, optional cell previews, references, original prompt, seeds, timings, and real output dimensions.
    </td>
  </tr>
</table>

The Director also shows the completed image with its generated seed. From there you can rerun with a new seed, rerun the exact seed, or keep that seed while editing the prompt. Optional TAEH3 previews update without blocking sampling and open into a full-size lightbox.

## Quick start

1. Open [`example_workflows/H3_Studio_Unified_Image.json`](example_workflows/H3_Studio_Unified_Image.json) in ComfyUI.
2. Select the installed FL2VA, REF2VA, 32B H3 text encoder, and video VAE in **H3 models · lazy route loader**.
3. Write a prompt in the **Image Director**. Add references only when the image actually needs them.
4. Assign each reference a narrow role and say what belongs to it: `Keep the identity and pose from @Image1; transfer only the jacket from @Image2.`
5. Choose a sampling profile, resolution mode, frame profile, and seed behavior, then queue.

The workflow opens with zero placeholder images and is immediately usable for text-to-image.

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
git clone --branch v0.1.0-alpha.12 --depth 1 https://github.com/thaakeno/ComfyUI-MiniMax-H3-Studio.git
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
| LightX v0.1 LoRA, optional | `models/loras/` | [Kijai/MiniMax-H3_comfy](https://huggingface.co/Kijai/MiniMax-H3_comfy) |
| TAEH3 approximate preview, optional | `models/vae_approx/` | [Kijai/MiniMax-H3-TAE](https://huggingface.co/Kijai/MiniMax-H3-TAE) |
| PDD LoRA + heads, optional | `models/loras/`, `models/pdd_heads/` | [Mamad8 PDD](https://huggingface.co/Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8) |
| T=1 Image VAE, experimental | `models/vae/` | [Mamad8 Image VAE](https://huggingface.co/Mamad8/MiniMax-H3-Image-VAE) |

PDD also requires the separately installed [ComfyUI-MiniMaxH3-PDD-Mamad8](https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8) package. H3 Studio integrates its registered execution surface; it does not copy or bundle that GPL implementation.

## Profiles and acceleration

| Profile | Recipe | Intended use |
| --- | --- | --- |
| Base Quality | RES, 20 steps | Safest native quality baseline |
| Base Balanced | RES, 12 steps | Faster native comparison |
| LightX ER-SDE | LightX v0.1 at `0.75`, 4 steps | Empirical Kijai ComfyUI recipe |
| LightX SA-Solver | LightX v0.1 at `0.75`, 4 steps | Alternate stochastic empirical recipe |
| PDD 600 / 900 | Matching REF2VA student LoRA + heads, 4 steps | Optional accelerated reference work |

The LightX labels are deliberately marked empirical: they reproduce a current working ComfyUI recipe, not an official guarantee that one sampler is universally best. PDD is REF2VA-only and cannot run without a valid reference context.

Conditioning uses separate prompt, reference, VAE, and latent caches. Compatible current ComfyUI builds can use upstream chunked H3 VAE encode/decode without changing decoded output. NVFP4 32B conditioning is preferred when installed.

## Direct resolution

The Director offers two explicit planning modes:

- **Conservative:** keeps the older approximately 1 MP working area for predictable memory use.
- **Direct:** sends the aligned target canvas to H3 from 0.2 MP through approximately 8.5 MP.

The slider labels draft, recommended, extended, experimental, and extreme ranges and always shows the real aligned dimensions. Direct 2/4/8 MP generation is available for experimentation, but H3 Base is not a dedicated super-resolution model. Very large canvases can raise attention cost, decode time, RAM, VRAM, and failure risk without proportional detail gains.

## Decode choices

The Director exposes the decoder separately from sampling speed:

- **Original H3 Video VAE:** the quality/default path. Choose 5, 9, 13, or 20 temporal frames; more candidates increase sampling and decoding work.
- **T=1 Image VAE:** the fastest decode path. It samples and decodes one still latent through Mamad8's optional experimental image VAE, but may soften typography, hair, fine contours, and microtexture.

Current ComfyUI automatically uses its upstream chunked H3 VAE path when available. That path sharply lowers peak decode memory with output-identical pixels, but upstream measurements show approximately unchanged decode speed. H3 Studio therefore reports it as a memory optimization and logs the actual decode duration instead of presenting it as a speed switch.

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

Local checks cover Python and frontend syntax, deterministic compilation, state migration, workflow regeneration/schema, node registration, route validation, PNG metadata restoration, and artifact consistency. CUDA speed, peak memory, model availability, and visual quality still require a real GPU run with the exact installed ComfyUI build.

If generation fails, open an [issue](https://github.com/thaakeno/ComfyUI-MiniMax-H3-Studio/issues) with the full traceback, ComfyUI version, GPU/VRAM, selected model filenames, route, profile, resolution, and a workflow JSON or metadata PNG when safe.

## Aggregate generation counter

After a still is successfully saved through **H3 Studio Save Image**, H3 Studio adds the actual output batch size to an in-memory batch. Every ten images—or after one minute—it sends only `{ "count": N, "schema": 1 }` in a background thread. It never sends prompts, images, references, filenames, workflows, seeds, hardware, usernames, paths, or installation identifiers. Failures are silent and cannot delay generation.

To opt out, set `H3STUDIO_TELEMETRY=0` before starting ComfyUI, or create an empty `.h3studio-telemetry-disabled` file in this repository. The endpoint can be self-hosted with the deployable [Cloudflare Worker](telemetry/README.md).

The public counter runs at [`h3-studio-counter.h3-studio-counter.workers.dev`](https://h3-studio-counter.h3-studio-counter.workers.dev/v1/count), and its live aggregate appears in the badge at the top of this README.

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

H3 Studio adapts the ordered media interaction and mention-editor foundations from [ComfyUI-MiniMaxH3-Easy](https://github.com/nkxx188/ComfyUI-MiniMaxH3-Easy) under MIT, and resolution/decode/workflow foundations from [ComfyUI-MiniMax-H3-Image-Studio](https://github.com/astropuzzo/ComfyUI-MiniMax-H3-Image-Studio) under the Unlicense. Earlier internal H3 Studio prototypes by Alier informed the Director's role-aware workflow and product hierarchy.

Kijai and Mamad8 model artifacts and optional nodes remain external works under their published terms. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for the exact boundaries. This independent project is not endorsed by MiniMax, ComfyUI, or the referenced projects.

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

## License

Original H3 Studio code is available under the [MIT License](LICENSE). Adapted files retain their upstream notices and terms; external models and optional custom nodes retain their own licenses.
