# Node reference

## Normal workflow

### H3 Studio · Image Director

Owns the prompt, integrated image uploads, ordered references, roles, retention policies, aspect ratio, megapixels, seed, enhancement mode, and route intent. Its **Add images** action uploads directly to ComfyUI input storage, renders a thumbnail, and assigns the next `@Image N`; external image links remain optional. Prompt shaping can preserve the exact wording, build a clear one-line H3 instruction, or build a four-section production brief. It returns a typed context, compiled prompt, serialized state, dimensions, seed, and diagnostics.

Friendly prompt references use `@Image 1`; runtime H3 conditioning receives `<Picture 1>`. Missing or disabled references produce actionable validation rather than an opaque encoder failure.

The Director also owns an optional **Custom LoRAs** stack. It discovers installed files from `ComfyUI/models/loras/`, supports up to six ordered H3-compatible model LoRAs, and persists each file, enabled state, order, and strength with the workflow. Custom LoRAs are applied after the selected Base/LightX/PDD speed path. On current ComfyUI they use bypass-forward injection so quantized H3 base weights are not merged and requantized. The active LightX/PDD acceleration artifact cannot be added a second time through the custom stack.

### H3 Studio · Model Loader

Loads the Qwen3-VL MiniMax text encoder and video VAE once. FL2VA and REF2VA transformer names are stored in a bundle and loaded lazily when the route asks for one. A full Qwen3-VL analyzer/writer and Mamad8's experimental T=1 Image VAE are optional explicit selectors; nothing downloads automatically. Unchanged model selections reuse the process-level Studio bundle instead of rebuilding the same CLIP/VAE objects after node recreation.

On low-RAM hosts, the loader reports when selected model files live in `/dev/shm`. tmpfs consumes ordinary host RAM, so keeping tens of gigabytes of H3 safetensors there can compete with ComfyUI's staged tensors and make otherwise fast model loads thrash for minutes.

### H3 Studio · Condition & Route

Consumes the model bundle and Studio context. It selects the route, encodes the production brief and images once, prepares the temporal latent, loads the selected transformer, and returns ordinary ComfyUI model/conditioning/latent/VAE values plus a typed generation bundle.

Prompt, reference-VAE, source-VAE and latent caches remain independent. On a text-conditioning cache miss, Studio asks ComfyUI to fully materialize the H3 32B text encoder for the encode, then targets only that patcher for release so the selected diffusion model gets the VRAM next. Cache hits skip the encode and residency handoff entirely. If full residency is unavailable, the optimization falls back to ComfyUI DynamicVRAM rather than failing the generation.

### H3 Studio · Sampling Preset

Builds model sampling, sampler, and sigma values for conservative base profiles or explicitly labeled acceleration profiles. Base Quality (`RES 20`) is the default.

The current LightX profile resolves the official `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` adapter from `models/loras/` and uses its eight-step FL2V/FL2VA path. The older Kijai LightX v0.1 ER-SDE and SA-Solver four-step recipes remain available for reproducibility. LightX profiles are rejected when the Studio request resolves to REF2VA so an FL2V adapter cannot be silently applied to the wrong transformer route.

LightX and custom LoRAs share the modern ComfyUI bypass-forward path. Multiple bypass adapters are explicitly preserved as one additive injection stack; applying a custom LoRA no longer replaces an already-active LightX injection. Unchanged acceleration and custom-LoRA stacks are cached so prompt/seed reruns do not reload their files or rebuild patch graphs.

Mamad8 PDD checkpoint-600/900 profiles are REF2VA-only: the preset detects the separately installed GPL node package, pairs the matching local student LoRA and heads bank, and delegates patching and trained-block scheduling to those registered nodes. Missing dependencies fail with corrective instructions and never alter Base behavior.

After sampling settings and all adapters are resolved, Studio asks ComfyUI to fully materialize the final patched H3 diffusion model before KSampler starts. This moves the expensive first materialization out of the opaque `Model Initializing` phase and prevents repeated layer streaming when the complete W4A8 model fits. It remains a nonfatal optimization: insufficient VRAM falls back to DynamicVRAM.

### H3 Studio · Exact Frame Decode

Decodes the complete temporal profile associated with the H3 latent, retains the natural requested packet, and emits a recommended frame index with a report.

MiniMax H3's original video VAE uses a large 36-layer ViT3D decoder with internal spatial tiling. With a partially resident VAE, DynamicVRAM can otherwise stream the same decoder weights again across many tiles even for a short 1/5-frame packet. Studio therefore fully materializes the selected VAE before entering the unchanged upstream decode path. The existing ComfyUI chunking, temporal semantics, tile geometry, and output pixels are left alone; if the full VAE cannot fit, decoding falls back to normal ComfyUI behavior.

### H3 Studio · Single Image Output

Selects one still using the decoder recommendation, fixed indices, quality/stability metrics, or optional source similarity. Debug candidate batches are off by default.

## Advanced nodes

`H3StudioOutput` unpacks a typed generation bundle for custom graphs. `H3StudioContextInspector` exposes prompt, route/dimension summary, and seed. Advanced Resolution exposes custom dimensions and native-cap control. Advanced Sampling exposes sampler, scheduler, steps, denoise, H3 AV shifts, and beta schedule parameters.

Separate Text to Image, Image to Image, Reference Edit, and Combined Prepare nodes remain available for expert graphs and compatibility. The combined Director/Condition path is preferred because it keeps routing and reference state coherent.

`H3StudioWorkflowNote` is documentation-only and never participates in generation.

### H3 Studio · Benchmark Lab

Builds a guarded **profile × resolution × repeat** matrix rather than a fixed A/B. Two profiles still make a simple comparison; additional same-route profiles widen the matrix. Resolution targets accept direct values from 0.20 to 8.50 MP, repeats are explicit, and a generation-count guard rejects accidental large runs before conditioning or model patching.

The fixed-seed strategy is the fair default; row/image seed modes are explicitly diversity sweeps. Each cell reports the actual aligned dimensions, seed, selected profile, and CUDA-synchronized sampling time. Native-capped duplicate variants are reused only when profile, seed, dimensions, and prompt are identical.

Acceleration families must stay on compatible routes. Base-vs-LightX runs use an FL2VA Director context. Base-vs-PDD runs use REF2VA. LightX-vs-PDD in one matrix is rejected because their adapters target different H3 routes.

Its VAE mode samples one T=1 latent once and decodes that exact latent through the original H3 video VAE and optional Image VAE. This isolates decoder behavior instead of mixing sampling variance into the result.

### H3 Studio · Lazy output switch

Selects normal or benchmark output using ComfyUI lazy inputs. Only the chosen branch is requested, so benchmark mode cannot accidentally schedule the normal generation too.
