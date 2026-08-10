"""Stable constants and user-facing option tables."""

from __future__ import annotations

from typing import Final

VERSION: Final = "0.1.0-alpha.11"
STATE_SCHEMA_VERSION: Final = 9
CONTEXT_SCHEMA_VERSION: Final = 1

CANVAS_MULTIPLE: Final = 32
DEFAULT_MEGAPIXELS: Final = 1.0
MIN_MEGAPIXELS: Final = 0.20
# 8.5 MP covers UHD/4K-class 16:9 after H3's 32-pixel canvas alignment.
MAX_MEGAPIXELS: Final = 8.50
UHD_4K_MEGAPIXELS: Final = 3840 * 2160 / 1_000_000
NATIVE_MAX_PIXELS: Final = 768 * 1344
MAX_REFERENCE_IMAGES: Final = 9
DEFAULT_WIDTH: Final = 1024
DEFAULT_HEIGHT: Final = 1024
DEFAULT_SEED: Final = 0

MODE_AUTO: Final = "auto"
MODE_TEXT_TO_IMAGE: Final = "text_to_image"
MODE_IMAGE_TO_IMAGE: Final = "image_to_image"
MODE_REFERENCE_EDIT: Final = "reference_edit"
MODES: Final = (
    MODE_AUTO,
    MODE_TEXT_TO_IMAGE,
    MODE_IMAGE_TO_IMAGE,
    MODE_REFERENCE_EDIT,
)

ROUTE_AUTO: Final = "auto"
ROUTE_FL2VA: Final = "fl2va"
ROUTE_REF2VA: Final = "ref2va"
ROUTES: Final = (ROUTE_AUTO, ROUTE_FL2VA, ROUTE_REF2VA)

ENHANCE_OFF: Final = "off"
ENHANCE_SINGLE: Final = "single_prompt"
ENHANCE_COMPILE: Final = "compile_only"
ENHANCE_VLM: Final = "vlm"
ENHANCE_MODES: Final = (ENHANCE_OFF, ENHANCE_SINGLE, ENHANCE_COMPILE, ENHANCE_VLM)

REFERENCE_ROLES: Final = (
    "auto",
    "identity",
    "character",
    "face",
    "style",
    "composition",
    "pose",
    "outfit",
    "object",
    "environment",
    "layout",
    "typography",
    "color_palette",
    "lighting",
    "texture",
)

RETENTION_MARKERS: Final = (
    "fully_preserved",
    "partially_preserved",
    "attribute_transfer",
    "reference_only",
)

ASPECT_RATIOS: Final = {
    "1:1": (1, 1),
    "4:5": (4, 5),
    "5:4": (5, 4),
    "3:4": (3, 4),
    "4:3": (4, 3),
    "2:3": (2, 3),
    "3:2": (3, 2),
    "9:16": (9, 16),
    "16:9": (16, 9),
    "21:9": (21, 9),
    "custom": (0, 0),
}

SAMPLING_PROFILES: Final = {
    "base_quality_20": {
        "label": "Base Quality · RES 20",
        "sampler": "res_multistep",
        "scheduler": "simple",
        "steps": 20,
        "cfg": 1.0,
        "shift_video": 12.0,
        "shift_audio": 3.0,
        "experimental": False,
    },
    "base_balanced_12": {
        "label": "Base Balanced · RES 12",
        "sampler": "res_multistep",
        "scheduler": "simple",
        "steps": 12,
        "cfg": 1.0,
        "shift_video": 12.0,
        "shift_audio": 3.0,
        "experimental": False,
    },
    "lightx_er_sde_4": {
        "label": "LightX v0.1 · ER-SDE 4",
        "sampler": "er_sde",
        "scheduler": "simple",
        "steps": 4,
        "cfg": 1.0,
        "shift_video": 12.0,
        "shift_audio": 3.0,
        "lora_strength": 0.8,
        "experimental": True,
    },
    "lightx_sa_solver_4": {
        "label": "LightX v0.1 · SA-Solver 4",
        "sampler": "sa_solver",
        "scheduler": "simple",
        "steps": 4,
        "cfg": 1.0,
        "shift_video": 12.0,
        "shift_audio": 3.0,
        "lora_strength": 0.8,
        "experimental": True,
    },
    "pdd_ref2va_4_600": {
        "label": "Mamad8 PDD REF2VA · 4-step · ckpt 600",
        "sampler": "euler",
        "scheduler": "trained_blocks",
        "steps": 4,
        "cfg": 1.0,
        "shift_video": 12.0,
        "shift_audio": 3.0,
        "lora_strength": 2.0,
        "head_strength": 1.0,
        "experimental": True,
        "external_backend": "mamad8_pdd",
    },
    "pdd_ref2va_4_900": {
        "label": "Mamad8 PDD REF2VA · 4-step · ckpt 900",
        "sampler": "euler",
        "scheduler": "trained_blocks",
        "steps": 4,
        "cfg": 1.0,
        "shift_video": 12.0,
        "shift_audio": 3.0,
        "lora_strength": 2.0,
        "head_strength": 1.0,
        "experimental": True,
        "external_backend": "mamad8_pdd",
    },
}

PROMPT_SECTION_NAMES: Final = (
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
)

ROLE_KEYWORDS: Final = {
    "identity": ("identity", "same person", "same character", "recognizable", "likeness"),
    "face": ("face", "facial", "eyes", "jaw", "portrait", "head", "hair", "hairstyle", "haircut"),
    "character": ("character", "person", "man", "woman", "boy", "girl", "subject", "hero", "villain"),
    "style": ("style", "rendering", "aesthetic", "art direction", "linework", "anime"),
    "composition": ("composition", "framing", "layout", "camera angle", "perspective"),
    "pose": ("pose", "stance", "gesture", "body position"),
    "outfit": ("outfit", "clothes", "clothing", "wardrobe", "costume", "jacket", "dress"),
    "object": ("object", "thing", "product", "prop", "item", "accessory", "glasses", "vehicle", "weapon"),
    "environment": ("environment", "background", "location", "setting", "scene"),
    "layout": ("poster", "layout", "graphic design", "magazine", "advertisement"),
    "typography": ("typography", "text", "title", "logo", "lettering", "headline"),
    "color_palette": ("palette", "color", "colour", "grading", "saturation"),
    "lighting": ("lighting", "light", "shadow", "illumination", "exposure"),
    "texture": ("texture", "grain", "material", "surface", "hatching"),
}
