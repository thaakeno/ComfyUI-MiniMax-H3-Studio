# Third-party notices

ComfyUI-MiniMax-H3-Studio is an independent project inspired by three existing implementations.

## ComfyUI-MiniMaxH3-Easy

The ordered media interaction, virtual media-link behavior, prompt mention editor, inline reference chips, and parts of `web/h3studio_ui.js` are adapted from `nkxx188/ComfyUI-MiniMaxH3-Easy` under the MIT License.

Copyright (c) 2026 nkxx188

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Source: https://github.com/nkxx188/ComfyUI-MiniMaxH3-Easy

## ComfyUI-MiniMax-H3-Image-Studio

Resolution math, exact-frame decode concepts, still-selection strategies, sampling-profile organization, workflow validation ideas, and `h3studio/nodes/image_runtime.py` are adapted from `astropuzzo/ComfyUI-MiniMax-H3-Image-Studio`, released under the Unlicense/public-domain dedication.

Source: https://github.com/astropuzzo/ComfyUI-MiniMax-H3-Image-Studio

## H3 Studio Unified Image Director

The role-aware reference compiler, adherence controls, explicit model routing, aspect-ratio/megapixel UX, and structured prompt direction build on Alier's private `H3StudioUnifiedImageDirector_v1_3_7.py` and its paired workflow.

This repository does not include H3 Studio Hub and does not claim compatibility with it.

## Optional TAEH3 preview asset

The optional `taeh3.safetensors` checkpoint is distributed by Kijai under Apache-2.0 and is not bundled in this repository:
https://huggingface.co/Kijai/MiniMax-H3-TAE

The independent tiny-decoder integration uses ComfyUI's public wrapper APIs and the established tiny-autoencoder architecture described by madebyollin's MIT-licensed TAEHV project:
https://github.com/madebyollin/taehv

No ComfyUI-KJNodes source code is copied into this MIT-licensed repository.

## Optional Mamad8 PDD backend

The optional REF2VA PDD profiles interoperate with `mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8`, distributed under GPL-3.0:
https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8

H3 Studio does not bundle, copy, modify, or relicense that implementation. Its MIT-licensed adapter only discovers the node IDs registered by the separately installed package and invokes their public execution surface. The external package and its model artifacts remain separate dependencies under their own terms.

## Optional Mamad8 Image VAE

The experimental `minimax_h3_t1_image_vae_step1597.safetensors` image decoder is distributed separately by Mamad8 and is not bundled:
https://huggingface.co/Mamad8/MiniMax-H3-Image-VAE

H3 Studio only exposes an optional loader and identical-latent decoder comparison. The model remains under the terms published with its Hugging Face repository. It is restricted to `T=1` still-image experiments; the original H3 video VAE remains the default and the only supported multi-frame decoder.
