# Node reference

## Normal workflow

### H3 Studio · Image Director

Owns the prompt, integrated image uploads, ordered references, roles, retention policies, aspect ratio, megapixels, seed, enhancement mode, and route intent. Its **Add images** action uploads directly to ComfyUI input storage, renders a thumbnail, and assigns the next `@Image N`; external image links remain optional. Prompt shaping can preserve the exact wording, build a clear one-line H3 instruction, or build a four-section production brief. It returns a typed context, compiled prompt, serialized state, dimensions, seed, and diagnostics.

Friendly prompt references use `@Image 1`; runtime H3 conditioning receives `<Picture 1>`. Missing or disabled references produce actionable validation rather than an opaque encoder failure.

### H3 Studio · Model Loader

Loads the Qwen3-VL MiniMax text encoder and video VAE once. FL2VA and REF2VA transformer names are stored in a bundle and loaded lazily when the route asks for one. A full Qwen3-VL analyzer/writer and Mamad8's experimental T=1 Image VAE are optional explicit selectors; nothing downloads automatically. Switching releases the prior transformer and requests a soft cache cleanup.

### H3 Studio · Condition & Route

Consumes the model bundle and Studio context. It selects the route, encodes the production brief and images once, prepares the temporal latent, loads the selected transformer, and returns ordinary ComfyUI model/conditioning/latent/VAE values plus a typed generation bundle.

### H3 Studio · Sampling Preset

Builds model sampling, sampler, and sigma values for conservative base profiles or explicitly labeled experimental acceleration profiles. Base Quality (`RES 20`) is the default. Mamad8 PDD checkpoint-600/900 profiles are REF2VA-only: the preset detects the separately installed GPL node package, pairs the matching local student LoRA and heads bank, and delegates patching and trained-block scheduling to those registered nodes. Missing dependencies fail with corrective instructions and never alter Base behavior.

### H3 Studio · Exact Frame Decode

Decodes the complete temporal profile associated with the H3 latent, retains the natural requested packet, and emits a recommended frame index with a report.

### H3 Studio · Single Image Output

Selects one still using the decoder recommendation, fixed indices, quality/stability metrics, or optional source similarity. Debug candidate batches are off by default.

## Advanced nodes

`H3StudioOutput` unpacks a typed generation bundle for custom graphs. `H3StudioContextInspector` exposes prompt, route/dimension summary, and seed. Advanced Resolution exposes custom dimensions and native-cap control. Advanced Sampling exposes sampler, scheduler, steps, denoise, H3 AV shifts, and beta schedule parameters.

Separate Text to Image, Image to Image, Reference Edit, and Combined Prepare nodes remain available for expert graphs and compatibility. The combined Director/Condition path is preferred because it keeps routing and reference state coherent.

`H3StudioWorkflowNote` is documentation-only and never participates in generation.

### H3 Studio · Benchmark Lab

Compares any two sampling profiles across 0.40, 1.00, and 2.00 MP, including direct LightX-vs-PDD tests. The fixed-seed strategy is the fair default; per-image seeds are explicitly a diversity sweep. The node reports actual aligned dimensions, seed, selected profile, and CUDA-synchronized sampling time. Native-capped duplicate variants are reused only when profile, seed, dimensions, and prompt are identical.

Its VAE mode samples one T=1 latent once and decodes that exact latent through the original H3 video VAE and optional Image VAE. This isolates decoder behavior instead of mixing sampling variance into the result.

### H3 Studio · Lazy output switch

Selects normal or benchmark output using ComfyUI lazy inputs. Only the chosen branch is requested, so benchmark mode cannot accidentally schedule a seventh normal generation.
