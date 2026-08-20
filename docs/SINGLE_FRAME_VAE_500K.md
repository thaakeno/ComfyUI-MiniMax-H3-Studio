# MiniMax H3 Single-Frame VAE 500K

H3 Studio supports the 500K single-frame VAE through its existing **1-frame image VAE** profile.

## Recommended checkpoint

Use the ComfyUI-ready conversion:

- https://huggingface.co/Alissonerdx/MiniMax-H3-Single-Frame-VAE-500K-Comfy

Place the downloaded `.safetensors` file in:

```text
ComfyUI/models/vae/
```

Restart ComfyUI, select it in **H3 Studio Loader → image_vae**, then choose the **experimental image VAE | 1 frame** generation profile.

The original training release is here:

- https://huggingface.co/iamkaikai/MiniMax-H3-Single-Frame-VAE-500K

The original release is decoder-focused and is not the file H3 Studio expects for normal `VAELoader` use. H3 Studio intentionally hides an obvious `single_frame_decoder_500k` filename unless it also identifies itself as a Comfy conversion, and produces a targeted error if a 500K file cannot be loaded as a complete ComfyUI VAE.

## Runtime behavior

The normal MiniMax H3 video VAE remains the default and is never replaced globally. The 500K VAE is loaded lazily only when the 1-frame image profile is selected.

For the 500K checkpoint, H3 Studio Auto decode uses the larger **512 / 64** still-image tile profile. If that profile hits a real CUDA OOM, H3 Studio clears the soft cache and retries once with the normal **256 / 64** geometry. Manual tile settings always override Auto and are never rewritten.

Legacy Mamad8 T=1 image-VAE checkpoints remain supported and keep the existing **256 / 64** Auto geometry.

## Compatibility

Filename detection accepts normal H3 image-VAE names containing `image_vae`, `t1`, or `single_frame`, so users do not need to rename the 500K Comfy checkpoint. The 500K conversion is preferred at the top of the optional image-VAE list when installed, while **Disabled - original H3 video VAE only** remains the default selection.
