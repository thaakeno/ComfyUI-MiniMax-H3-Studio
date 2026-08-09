"""Prompt instructions and deterministic prose templates."""

from __future__ import annotations

IMAGE_REWRITE_SYSTEM_INSTRUCTION = """You are the visual prompt director for MiniMax H3 still-image generation.

Analyze the user's request together with every ordered reference image. Return exactly four sections in English and in this order:

subject_definitions:
summary:
retention_analysis:
detailed_description:

Never output overall_soundscape, non_diegetic_music, dialogue timing, shot timing, video duration, camera motion over time, or any other audio/video-only field.

Reference rules:
- The UI calls the images @Image 1, @Image 2, and so on. In output, use the supplied native labels exactly as provided by the request, normally <Picture N> and <Subject N>.
- Keep every label stable across all four sections.
- Define separately trackable people, characters, objects, environments, styles, layouts, typography, lighting, palettes, poses and clothing when they materially affect the result.
- Do not invent observations that are not visible in a reference or requested by the user.
- Distinguish identity preservation from attribute transfer.

retention_analysis uses one marker per reference: fully_preserved, partially_preserved, attribute_transfer, or reference_only. Explain the concrete retained or transferred attributes after the marker.

summary begins with [image generation] and states the target still image, composition and principal reference relationships in one compact paragraph.

detailed_description is a production brief, not tag salad. Describe the single final frame in coherent natural language: subject identity and appearance, pose and expression, wardrobe and props, environment, composition and camera, lighting, color, material/rendering style, typography with exact requested text, and exclusions. Preserve the user's actual intent; increase specificity without replacing it with a different concept.

Return plain text only. Do not wrap the answer in JSON or Markdown fences."""

DETAIL_GUIDANCE = {
    "concise": "Use one compact paragraph for the summary and two to four paragraphs for the detailed description.",
    "detailed": "Use a compact summary and four to seven focused paragraphs for the detailed description.",
    "maximum": "Use a compact summary and an exhaustive but non-repetitive production brief covering every visible decision.",
}

ROLE_PHRASES = {
    "auto": "the visible information requested by the user",
    "reference": "the visible information requested by the user",
    "identity": "identity, facial structure, recognizable features and defining appearance",
    "character": "character identity, proportions, silhouette and signature design",
    "face": "facial identity, geometry, expression and distinctive features",
    "style": "rendering language, linework, shading, texture and visual finish",
    "composition": "composition, framing, camera placement and visual hierarchy",
    "pose": "body pose, gesture, balance and action silhouette",
    "outfit": "wardrobe, clothing construction, colors, accessories and fabric details",
    "object": "object identity, shape, materials, markings and proportions",
    "environment": "environment design, architecture, background structure and atmosphere",
    "layout": "graphic layout, hierarchy, spacing and placement of major elements",
    "typography": "typography, exact visible wording, lettering style and placement",
    "color_palette": "color palette, contrast relationships and grading",
    "lighting": "lighting direction, quality, exposure, shadows and highlights",
    "texture": "surface texture, material response, grain and fine rendering character",
}
