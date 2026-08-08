# Node reference

## Normal workflow

### H3 Studio · Image Director

Owns the prompt, ordered images, reference roles, retention policies, aspect ratio, megapixels, seed, enhancement mode, and route intent. Returns a typed context, compiled prompt, serialized state, dimensions, seed, and diagnostics.

Friendly prompt references use `@Image 1`; runtime H3 conditioning receives `<Picture 1>`. Missing or disabled references produce actionable validation rather than an opaque encoder failure.

### H3 Studio · Model Loader

Loads the Qwen3-VL MiniMax text encoder and video VAE once. FL2VA and REF2VA transformer names are stored in a bundle and loaded lazily when the route asks for one. Switching releases the prior transformer and requests a soft cache cleanup.

### H3 Studio · Condition & Route

Consumes the model bundle and Studio context. It selects the route, encodes the production brief and images once, prepares the temporal latent, loads the selected transformer, and returns ordinary ComfyUI model/conditioning/latent/VAE values plus a typed generation bundle.

### H3 Studio · Sampling Preset

Builds model sampling, sampler, and sigma values for conservative base profiles or explicitly labeled experimental acceleration profiles. Base Quality (`RES 20`) is the default.

### H3 Studio · Exact Frame Decode

Decodes the complete temporal profile associated with the H3 latent, retains the natural requested packet, and emits a recommended frame index with a report.

### H3 Studio · Single Image Output

Selects one still using the decoder recommendation, fixed indices, quality/stability metrics, or optional source similarity. Debug candidate batches are off by default.

## Advanced nodes

`H3StudioOutput` unpacks a typed generation bundle for custom graphs. `H3StudioContextInspector` exposes prompt, route/dimension summary, and seed. Advanced Resolution exposes custom dimensions and native-cap control. Advanced Sampling exposes sampler, scheduler, steps, denoise, H3 AV shifts, and beta schedule parameters.

Separate Text to Image, Image to Image, Reference Edit, and Combined Prepare nodes remain available for expert graphs and compatibility. The combined Director/Condition path is preferred because it keeps routing and reference state coherent.

`H3StudioWorkflowNote` is documentation-only and never participates in generation.
