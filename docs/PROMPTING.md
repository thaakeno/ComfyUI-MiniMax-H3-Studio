# Prompting MiniMax H3 Studio

Write the visual objective naturally. Use `@Image N` only where a connected reference has a concrete job, then make that job explicit in its card.

## Production-brief contract

The compiler emits exactly four sections in this order:

1. `subject_definitions` maps every enabled reference to a visual responsibility.
2. `summary` states `[image generation]` and the requested deliverable.
3. `retention_analysis` states how each reference must be preserved or transferred.
4. `detailed_description` gives coherent scene, subject, composition, lighting, material, text, and fidelity instructions.

Image-only prompts do not include `overall_soundscape` or `non_diegetic_music`. H3's internal audiovisual architecture does not make irrelevant audio prose useful to a still-image request.

## Strong reference assignment

```text
Use @Image 1 as the exact character identity.
Transfer the gothic ink rendering from @Image 2.
Use @Image 3 for the poster hierarchy and typography placement.
Create a 9:16 promotional anime key visual with the title “DIO'S REQUIEM”.
```

Set Image 1 to `identity / fully_preserved`, Image 2 to `style / attribute_transfer`, and Image 3 to `layout / attribute_transfer`. The compiled result can then say what each reference defines without guessing from image order alone.

## Text-to-image

Disconnect all image references and describe the still. Auto mode selects FL2VA. The compiler omits empty reference sections where appropriate and does not manufacture fake `@Image` labels.

## Two-pass Qwen3-VL direction

The first pass uses a full native ComfyUI Qwen3-VL checkpoint to inspect analyzer-only image copies and produce factual source descriptions, roles, and retention. Those records are cached by analyzer, prompt, detail setting, and image pixels. Changing only the seed does not inspect the images again.

The optional **Detailed prompt expansion** is text-only. It reuses the analyzer by default or uses a separately selected full Qwen3-VL 8B checkpoint, targets 200-450 words, accepts valid instructions from 180 words, validates image assignments, directional/contact constraints, and named-style traits, then retries once only when substantive validation fails. The chosen output format still decides whether the final H3 prompt is a one-line instruction or the four-section production brief.

The H3 ConvRot 32B Qwen encoder remains the conditioning encoder. Its generation head is absent, so it cannot replace either full analyzer/writer checkpoint.

## Common failures

If `@Image 3` is mentioned with only two connected images, add the missing image or fix the ordinal. If identity drifts, choose an identity/face role, use `fully_preserved`, increase adherence, and state immutable traits. If references fight, narrow each image to one responsibility. If typography matters, quote the exact text and describe hierarchy, location, case, outline, and contrast.
