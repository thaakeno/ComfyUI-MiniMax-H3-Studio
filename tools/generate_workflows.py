"""Generate the maintained MiniMax H3 Studio workflow and sampling subgraph.

The layout deliberately keeps the DOM-backed Director at the top level. Only
stable sampling and decode plumbing is placed inside the subgraph, so ComfyUI
does not need to promote a custom browser widget through a subgraph boundary.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "example_workflows" / "H3_Studio_Unified_Image.json"
SUBGRAPH_PATH = ROOT / "subgraphs" / "H3_Studio_Sampling_and_Decode.json"
BLUEPRINT_ID = "8345c465-1de3-58e2-84dd-7bfbe9263ab2"
SUBGRAPH_ID = "5930b00d-9f8e-4b87-9cb5-ff5f7cf3b30a"
WORKFLOW_ID = "51ffc0bb-1b7a-4a1c-a183-1ce99edb4e5e"


def socket(name: str, kind: str, link=None, *, shape: int | None = None, widget: str | None = None):
    value = {"name": name, "type": kind, "link": link}
    if shape is not None:
        value["shape"] = shape
    if widget:
        value["widget"] = {"name": widget}
    return value


def output(name: str, kind: str, links=None, *, slot_index: int | None = None):
    value = {"name": name, "type": kind, "links": links}
    if slot_index is not None:
        value["slot_index"] = slot_index
    return value


def node(
    node_id: int,
    kind: str,
    title: str,
    pos,
    size,
    *,
    order: int,
    inputs=None,
    outputs=None,
    widgets=None,
    properties=None,
    color: str | None = None,
    bgcolor: str | None = None,
):
    value = {
        "id": node_id,
        "type": kind,
        "pos": list(pos),
        "size": list(size),
        "flags": {},
        "order": order,
        "mode": 0,
        "inputs": inputs or [],
        "outputs": outputs or [],
        "title": title,
        "properties": properties or {"Node name for S&R": kind},
        "widgets_values": widgets or [],
    }
    if color:
        value["color"] = color
    if bgcolor:
        value["bgcolor"] = bgcolor
    return value


def note(node_id: int, title: str, section: str, text: str, pos, size, order: int):
    return node(
        node_id,
        "H3StudioWorkflowNote",
        title,
        pos,
        size,
        order=order,
        inputs=[socket("section", "COMBO", widget="section"), socket("text", "STRING", widget="text")],
        widgets=[section, text],
        color="#22322f",
        bgcolor="#17211f",
        properties={
            "Node name for S&R": "H3StudioWorkflowNote",
            "purpose": "Documentation only; never enters the generation graph.",
        },
    )


class Links:
    def __init__(self):
        self.items = []
        self.next_id = 1

    def add(self, origin, origin_slot, target, target_slot, kind):
        link_id = self.next_id
        self.next_id += 1
        self.items.append([link_id, origin, origin_slot, target, target_slot, kind])
        return link_id


def director_widgets(state_json: str):
    values = [
        "image",
        "Describe the final still image. Upload references here only when they have a specific visual job.",
        "Custom",
        "1:1",
        1024,
        1024,
        5.0,
        False,
        24.0,
        "first",
        "2k",
        "index",
        1.0,
        42,
        "vlm",
        0.85,
        "auto",
        "base_quality_20",
        "recommended_5",
        "",
        state_json,
        "",
    ]
    for _index in range(1, 10):
        values.extend(["image", "", "auto", "attribute_transfer", ""])
    return values


def build_subgraph():
    links = []

    def add(link_id, origin, origin_slot, target, target_slot, kind):
        links.append(
            {
                "id": link_id,
                "origin_id": origin,
                "origin_slot": origin_slot,
                "target_id": target,
                "target_slot": target_slot,
                "type": kind,
            }
        )
        return link_id

    nodes = [
        node(
            101,
            "H3StudioContextSamplingPreset",
            "Director-selected sampling profile",
            [40, 40],
            [340, 100],
            order=0,
            inputs=[socket("model", "MODEL", 1), socket("studio_context", "H3_STUDIO_CONTEXT", 17)],
            outputs=[
                output("model", "MODEL", [6]),
                output("sampler", "SAMPLER", [7]),
                output("sigmas", "SIGMAS", [8]),
                output("sampling_info", "STRING", None),
            ],
            widgets=[],
        ),
        node(
            102,
            "BasicGuider",
            "Positive guider",
            [450, 60],
            [270, 72],
            order=1,
            inputs=[socket("model", "MODEL", 6), socket("conditioning", "CONDITIONING", 2)],
            outputs=[output("GUIDER", "GUIDER", [9])],
            widgets=[],
        ),
        node(
            103,
            "RandomNoise",
            "Studio seed",
            [50, 220],
            [280, 82],
            order=2,
            inputs=[socket("noise_seed", "INT", 5, widget="noise_seed")],
            outputs=[output("NOISE", "NOISE", [10])],
            widgets=[42, "fixed"],
        ),
        node(
            104,
            "SamplerCustomAdvanced",
            "Sample H3 still packet",
            [790, 150],
            [330, 150],
            order=3,
            inputs=[
                socket("noise", "NOISE", 10),
                socket("guider", "GUIDER", 9),
                socket("sampler", "SAMPLER", 7),
                socket("sigmas", "SIGMAS", 8),
                socket("latent_image", "LATENT", 3),
            ],
            outputs=[output("output", "LATENT", [11]), output("denoised_output", "LATENT", None)],
            widgets=[],
        ),
        node(
            105,
            "H3StudioDecode",
            "Exact frame decode",
            [1190, 150],
            [310, 104],
            order=4,
            inputs=[socket("samples", "LATENT", 11), socket("vae", "VAE", 4)],
            outputs=[
                output("frames", "IMAGE", [12]),
                output("decoded_frames", "INT", None),
                output("decode_info", "STRING", [15]),
                output("recommended_index", "INT", [13]),
            ],
            widgets=[],
        ),
        node(
            106,
            "H3StudioFrameSelector",
            "Select final still",
            [1570, 100],
            [430, 360],
            order=5,
            inputs=[
                socket("frames", "IMAGE", 12),
                socket("strategy", "COMBO", widget="strategy"),
                socket("manual_index", "INT", widget="manual_index"),
                socket("skip_first_frames", "INT", widget="skip_first_frames"),
                socket("candidate_start", "FLOAT", widget="candidate_start"),
                socket("candidate_end", "FLOAT", widget="candidate_end"),
                socket("similarity_weight", "FLOAT", widget="similarity_weight"),
                socket("top_k", "INT", widget="top_k"),
                socket("source_image", "IMAGE", None),
                socket("emit_candidate_batch", "BOOLEAN", None, widget="emit_candidate_batch"),
                socket("recommended_index", "INT", 13),
            ],
            outputs=[
                output("selected_image", "IMAGE", [14]),
                output("candidate_batch_debug", "IMAGE", None),
                output("selected_index", "INT", None),
                output("selected_score", "FLOAT", None),
                output("selection_report", "STRING", [16]),
            ],
            widgets=["decode_recommended", 0, 0, 0.0, 1.0, 0.6, 4, False],
        ),
    ]
    add(1, -10, 0, 101, 0, "MODEL")
    add(2, -10, 1, 102, 1, "CONDITIONING")
    add(3, -10, 2, 104, 4, "LATENT")
    add(4, -10, 3, 105, 1, "VAE")
    add(5, -10, 4, 103, 0, "INT")
    add(6, 101, 0, 102, 0, "MODEL")
    add(7, 101, 1, 104, 2, "SAMPLER")
    add(8, 101, 2, 104, 3, "SIGMAS")
    add(9, 102, 0, 104, 1, "GUIDER")
    add(10, 103, 0, 104, 0, "NOISE")
    add(11, 104, 0, 105, 0, "LATENT")
    add(12, 105, 0, 106, 0, "IMAGE")
    add(13, 105, 3, 106, 10, "INT")
    add(14, 106, 0, -20, 0, "IMAGE")
    add(15, 105, 2, -20, 1, "STRING")
    add(16, 106, 4, -20, 2, "STRING")
    add(17, -10, 5, 101, 1, "H3_STUDIO_CONTEXT")
    inputs = [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"h3studio-input-{name}")),
            "name": name,
            "type": kind,
            "linkIds": [link_id],
            "pos": [-160, 80 + index * 52],
        }
        for index, (name, kind, link_id) in enumerate(
            [
                ("model", "MODEL", 1),
                ("positive", "CONDITIONING", 2),
                ("h3_latent", "LATENT", 3),
                ("video_vae", "VAE", 4),
                ("seed", "INT", 5),
                ("studio_context", "H3_STUDIO_CONTEXT", 17),
            ],
            1,
        )
    ]
    outputs = [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"h3studio-output-{name}")),
            "name": name,
            "type": kind,
            "linkIds": [link_id],
            "pos": [2160, 180 + index * 52],
        }
        for index, (name, kind, link_id) in enumerate(
            [("image", "IMAGE", 14), ("decode_info", "STRING", 15), ("selection_report", "STRING", 16)]
        )
    ]
    return {
        "id": SUBGRAPH_ID,
        "version": 1,
        "state": {"lastGroupId": 0, "lastNodeId": 106, "lastLinkId": 17, "lastRerouteId": 0},
        "revision": 0,
        "config": {},
        "name": "H3 Studio · Sampling and Exact Still Decode",
        "inputNode": {"id": -10, "bounding": [-190, 40, 120, 360]},
        "outputNode": {"id": -20, "bounding": [2130, 120, 140, 240]},
        "inputs": inputs,
        "outputs": outputs,
        "widgets": [],
        "nodes": nodes,
        "groups": [
            {
                "id": 1,
                "title": "01 · H3 sampling",
                "bounding": [10, 0, 740, 350],
                "color": "#355b54",
                "font_size": 22,
                "flags": {},
            },
            {
                "id": 2,
                "title": "02 · Decode the temporal packet",
                "bounding": [760, 20, 760, 330],
                "color": "#3f536b",
                "font_size": 22,
                "flags": {},
            },
            {
                "id": 3,
                "title": "03 · Choose one still",
                "bounding": [1530, 20, 520, 490],
                "color": "#66553d",
                "font_size": 22,
                "flags": {},
            },
        ],
        "links": links,
        "extra": {
            "documentation": "The Director stays outside this subgraph because ComfyUI does not reliably promote custom DOM widgets."
        },
        "category": "H3 Studio",
        "description": "Director-selected H3 sampling, exact temporal decode, and stable still selection.",
    }


def build_subgraph_blueprint():
    subgraph = build_subgraph()
    wrapper = node(
        1,
        SUBGRAPH_ID,
        subgraph["name"],
        [120, 120],
        [620, 420],
        order=0,
        inputs=[socket(item["name"], item["type"]) for item in subgraph["inputs"]],
        outputs=[output(item["name"], item["type"], []) for item in subgraph["outputs"]],
        widgets=[],
        properties={"cnr_id": "comfy-core", "ver": "0.30.0"},
    )
    return {
        "id": BLUEPRINT_ID,
        "revision": 0,
        "last_node_id": 1,
        "last_link_id": 0,
        "nodes": [wrapper],
        "links": [],
        "groups": [],
        "definitions": {"subgraphs": [subgraph]},
        "config": {},
        "extra": {"workflowRendererVersion": "LG"},
        "version": 0.4,
    }


def build_workflow():
    links = Links()
    state = {
        "schema_version": 10,
        "prompt": "Describe the final still image.",
        "references": [],
        "prompt_options": {
            "enhance_mode": "compile_only",
            "analyze_images": True,
            "deep_enhancement": True,
            "analyzer_resolution": 512,
            "adherence": 0.85,
            "detail_level": "detailed",
            "preserve_user_text": True,
            "infer_roles": True,
            "system_instruction": "",
            "analyzer_model": "",
            "analyzer_device": "auto",
            "analyzer_quantization": "auto",
            "analyzer_max_tokens": 1800,
            "analyzer_keep_loaded": False,
        },
        "generation": {
            "mode": "auto",
            "route": "auto",
            "seed": 42,
            "seed_locked": False,
            "aspect_ratio": "1:1",
            "megapixels": 1.0,
            "custom_width": 1024,
            "custom_height": 1024,
            "cap_native_resolution": True,
            "sampling_profile": "base_quality_20",
            "frame_profile": "recommended_5",
            "frame_selection": "decode_recommended",
            "reference_short_edge": 2048,
            "source_image_ordinal": 1,
        },
        "ui": {"advanced_open": False, "reference_details": {}},
    }
    state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    virtual_links = []

    l_context_condition = links.add(10, 0, 12, 1, "H3_STUDIO_CONTEXT")
    l_bundle_condition = links.add(11, 0, 12, 0, "H3_STUDIO_BUNDLE")
    l_bundle_director = links.add(11, 0, 10, 23, "H3_STUDIO_BUNDLE")
    l_model_preview = links.add(12, 0, 16, 0, "MODEL")
    l_preview_sub = links.add(16, 0, 13, 0, "MODEL")
    l_positive_sub = links.add(12, 2, 13, 1, "CONDITIONING")
    l_latent_sub = links.add(12, 3, 13, 2, "LATENT")
    l_vae_sub = links.add(12, 4, 13, 3, "VAE")
    l_seed_sub = links.add(10, 5, 13, 4, "INT")
    l_context_sub = links.add(10, 0, 13, 5, "H3_STUDIO_CONTEXT")
    l_normal_switch = links.add(13, 0, 19, 1, "IMAGE")
    l_bundle_ab = links.add(11, 0, 17, 0, "H3_STUDIO_BUNDLE")
    l_context_ab = links.add(10, 0, 17, 1, "H3_STUDIO_CONTEXT")
    l_context_save = links.add(10, 0, 15, 1, "H3_STUDIO_CONTEXT")
    l_context_comparison = links.add(10, 0, 30, 1, "H3_STUDIO_CONTEXT")
    l_ab_switch = links.add(17, 0, 19, 2, "IMAGE")
    l_selected_preview = links.add(19, 0, 14, 0, "IMAGE")
    l_selected_save = links.add(19, 0, 15, 0, "IMAGE")
    l_selected_comparison = links.add(19, 0, 30, 0, "IMAGE")

    director_inputs = [
        socket("mode", "COMBO", widget="mode"),
        socket("prompt", "STRING", widget="prompt"),
        socket("resolution", "COMBO", widget="resolution"),
        socket("aspect_ratio", "COMBO", widget="aspect_ratio"),
        socket("width", "INT", widget="width"),
        socket("height", "INT", widget="height"),
        socket("seconds", "FLOAT", widget="seconds"),
        socket("advanced", "BOOLEAN", widget="advanced"),
        socket("fps", "FLOAT", widget="fps"),
        socket("keyframe_role", "COMBO", widget="keyframe_role"),
        socket("ref_image_size", "COMBO", widget="ref_image_size"),
        socket("reference_mention_mode", "COMBO", widget="reference_mention_mode"),
        socket("megapixels", "FLOAT", widget="megapixels"),
        socket("seed", "INT", widget="seed"),
        socket("enhance_mode", "COMBO", widget="enhance_mode"),
        socket("adherence", "FLOAT", widget="adherence"),
        socket("route", "COMBO", widget="route"),
        socket("sampling_profile", "COMBO", widget="sampling_profile"),
        socket("frame_profile", "COMBO", widget="frame_profile"),
        socket("analyzer_model", "STRING", widget="analyzer_model"),
        socket("studio_state", "STRING", widget="studio_state"),
        socket("media", "*", None, shape=7),
        socket("media_filename", "STRING", widget="media_filename"),
        socket("h3_bundle", "H3_STUDIO_BUNDLE", l_bundle_director),
    ]
    nodes = [
        node(
            10,
            "H3StudioDirector",
            "MiniMax H3 Studio · Image Director",
            [-1450, 220],
            [700, 780],
            order=0,
            inputs=director_inputs,
            outputs=[
                output(
                    "studio_context",
                    "H3_STUDIO_CONTEXT",
                    [l_context_condition, l_context_sub, l_context_ab, l_context_save, l_context_comparison],
                ),
                output("compiled_prompt", "STRING", None),
                output("state_json", "STRING", None),
                output("width", "INT", None),
                output("height", "INT", None),
                output("seed", "INT", [l_seed_sub]),
                output("diagnostics", "STRING", None),
            ],
            widgets=director_widgets(state_json),
            properties={
                "Node name for S&R": "H3StudioDirector",
                "h3studio_virtual_media_links": virtual_links,
                "h3studio_state": state_json,
                "h3studio_prompt_reference_doc": {"version": 1, "parts": [{"type": "text", "text": state["prompt"]}]},
            },
            color="#255049",
            bgcolor="#172d29",
        ),
        node(
            11,
            "H3StudioLoader",
            "H3 models · lazy route loader",
            [-520, 260],
            [560, 220],
            order=1,
            inputs=[
                socket("fl2va_model", "COMBO", widget="fl2va_model"),
                socket("ref2va_model", "COMBO", widget="ref2va_model"),
                socket("text_encoder", "COMBO", widget="text_encoder"),
                socket("video_vae", "COMBO", widget="video_vae"),
                socket("image_vae", "COMBO", widget="image_vae"),
                socket("image_analyzer", "COMBO", widget="image_analyzer"),
                socket("prompt_writer", "COMBO", widget="prompt_writer"),
            ],
            outputs=[
                output("h3_bundle", "H3_STUDIO_BUNDLE", [l_bundle_condition, l_bundle_director, l_bundle_ab]),
                output("clip", "CLIP", None),
                output("video_vae", "VAE", None),
                output("model_info", "STRING", None),
            ],
            widgets=[
                "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors",
                "minimax_h3_ref2va_pruned_w4a8_mixed.safetensors",
                "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                "minimax_h3_video_vae_fp16.safetensors",
                "Disabled - original H3 video VAE only",
                "Auto · Qwen3-VL 4B",
                "Same as image analyzer",
            ],
            color="#31475c",
            bgcolor="#202e3c",
        ),
        node(
            12,
            "H3StudioCondition",
            "Compile, condition, and route once",
            [-520, 560],
            [560, 150],
            order=2,
            inputs=[
                socket("h3_bundle", "H3_STUDIO_BUNDLE", l_bundle_condition),
                socket("studio_context", "H3_STUDIO_CONTEXT", l_context_condition),
            ],
            outputs=[
                output("model", "MODEL", [l_model_preview]),
                output("generation", "H3_STUDIO_GENERATION", None),
                output("positive", "CONDITIONING", [l_positive_sub]),
                output("h3_latent", "LATENT", [l_latent_sub]),
                output("video_vae", "VAE", [l_vae_sub]),
                output("requested_frames", "INT", None),
                output("run_info", "STRING", None),
            ],
            widgets=[],
            color="#53482c",
            bgcolor="#352e1d",
        ),
        node(
            16,
            "H3StudioTAEH3Preview",
            "Live preview · TAEH3 (optional)",
            [220, 260],
            [620, 620],
            order=3,
            inputs=[
                socket("model", "MODEL", l_model_preview),
                socket("enabled", "BOOLEAN", widget="enabled"),
                socket("tiny_vae", "COMBO", widget="tiny_vae"),
                socket("max_resolution", "INT", widget="max_resolution"),
                socket("jpeg_quality", "INT", widget="jpeg_quality"),
                socket("preview_every_n_steps", "INT", widget="preview_every_n_steps"),
            ],
            outputs=[output("model", "MODEL", [l_preview_sub])],
            widgets=[True, "taeh3.safetensors", 768, 90, 1],
            color="#31475c",
            bgcolor="#202e3c",
        ),
        node(
            13,
            SUBGRAPH_ID,
            "H3 Studio · Sampling + exact still",
            [220, 920],
            [620, 420],
            order=4,
            inputs=[
                socket("model", "MODEL", l_preview_sub),
                socket("positive", "CONDITIONING", l_positive_sub),
                socket("h3_latent", "LATENT", l_latent_sub),
                socket("video_vae", "VAE", l_vae_sub),
                socket("seed", "INT", l_seed_sub),
                socket("studio_context", "H3_STUDIO_CONTEXT", l_context_sub),
            ],
            outputs=[
                output("image", "IMAGE", [l_normal_switch]),
                output("decode_info", "STRING", None),
                output("selection_report", "STRING", None),
            ],
            widgets=[],
            properties={"cnr_id": "comfy-core", "ver": "0.30.0", "previewExposures": []},
            color="#3c514c",
            bgcolor="#24312f",
        ),
        node(
            14,
            "PreviewImage",
            "Final still · preview",
            [1030, 260],
            [440, 420],
            order=4,
            inputs=[socket("images", "IMAGE", l_selected_preview)],
            outputs=[],
            widgets=[],
            color="#3c514c",
            bgcolor="#24312f",
        ),
        node(
            15,
            "H3StudioSaveImage",
            "Final still · restorable PNG",
            [1030, 750],
            [440, 190],
            order=5,
            inputs=[
                socket("images", "IMAGE", l_selected_save),
                socket("studio_context", "H3_STUDIO_CONTEXT", l_context_save),
                socket("filename_prefix", "STRING", widget="filename_prefix"),
            ],
            outputs=[],
            widgets=["H3Studio/%date:yyyy-MM-dd%/H3"],
            color="#3c514c",
            bgcolor="#24312f",
        ),
        node(
            30,
            "H3StudioComparisonView",
            "Reference comparison · optional",
            [1030, 1010],
            [440, 420],
            order=6,
            inputs=[
                socket("images", "IMAGE", l_selected_comparison),
                socket("studio_context", "H3_STUDIO_CONTEXT", l_context_comparison),
            ],
            outputs=[],
            widgets=[],
            color="#3c514c",
            bgcolor="#24312f",
        ),
        node(
            17,
            "H3StudioABComparison",
            "Benchmark Lab - profiles / resolution / VAE",
            [-520, 1700],
            [780, 520],
            order=6,
            inputs=[
                socket("h3_bundle", "H3_STUDIO_BUNDLE", l_bundle_ab),
                socket("studio_context", "H3_STUDIO_CONTEXT", l_context_ab),
                socket("comparison_kind", "COMBO", widget="comparison_kind"),
                socket("profiles", "STRING", widget="profiles"),
                socket("megapixels", "STRING", widget="megapixels"),
                socket("repeats", "INT", widget="repeats"),
                socket("seed_strategy", "COMBO", widget="seed_strategy"),
                socket("seed_step", "INT", widget="seed_step"),
                socket("grid_cell_size", "INT", widget="grid_cell_size"),
                socket("max_generations", "INT", widget="max_generations"),
                socket("allow_large_matrix", "BOOLEAN", widget="allow_large_matrix"),
                socket("include_reference_context", "BOOLEAN", widget="include_reference_context"),
                socket("include_original_prompt", "BOOLEAN", widget="include_original_prompt"),
                socket("live_cell_previews", "BOOLEAN", widget="live_cell_previews"),
            ],
            outputs=[
                output("comparison_grid", "IMAGE", [l_ab_switch]),
                output("comparison_report", "STRING", None),
            ],
            widgets=[
                "Sampling profiles x resolution",
                "base_quality_20, lightx_er_sde_4",
                "0.40, 1.00, 2.00",
                1,
                "Same seed for all - fair comparison",
                1,
                640,
                24,
                False,
                True,
                True,
                True,
            ],
            color="#60467a",
            bgcolor="#332640",
        ),
        node(
            19,
            "H3StudioLazyImageSwitch",
            "Run mode - normal or benchmark only",
            [340, 1700],
            [420, 180],
            order=7,
            inputs=[
                socket("benchmark_enabled", "BOOLEAN", widget="benchmark_enabled"),
                socket("normal_image", "IMAGE", l_normal_switch),
                socket("benchmark_image", "IMAGE", l_ab_switch),
            ],
            outputs=[
                output("image", "IMAGE", [l_selected_preview, l_selected_save, l_selected_comparison]),
                output("selected_mode", "STRING", None),
            ],
            widgets=[False],
            color="#60467a",
            bgcolor="#332640",
        ),
        note(
            20,
            "START HERE · three-minute setup",
            "quick start",
            "## Make an image\n\n1. Write naturally in the **Director**.\n2. Add references only when needed; they become ordered `@Image1`, `@Image2`, … cards.\n3. Choose the image role, retention, aspect, resolution, and seed.\n4. Queue the workflow.\n\n> [!TIP]\n> With no references, Auto uses FL2VA text-to-image immediately. Multi-reference work uses REF2VA.",
            [-1450, -180],
            [500, 320],
            10,
        ),
        note(
            21,
            "Prompt enhancement · what actually happens",
            "settings",
            "## Two deliberate Qwen stages\n\n- **Analyze image pixels**: Qwen3-VL creates factual source descriptions and repairs automatic roles.\n- **Prompt enhancement**: a compact text-only Qwen pass turns the request and facts into a production direction.\n\nThe default writer is **Same as image analyzer**, so Auto 4B does both jobs with one loaded checkpoint. Select Auto 8B or an explicit file only when you accept staging a second model. Fingerprints and both stage caches survive normal reruns.",
            [-910, -180],
            [520, 320],
            11,
        ),
        note(
            22,
            "Routing · deliberate defaults",
            "settings",
            "## Auto is the safe default\n\n- **0 references:** FL2VA text-to-image\n- **1 anchor:** FL2VA image-to-image when requested\n- **Multiple references:** REF2VA\n\n> [!WARNING]\n> Forced routes are diagnostic controls. Invalid reference/route combinations are rejected before model work starts.",
            [-370, -180],
            [520, 320],
            12,
        ),
        note(
            24,
            "Why the Director is not hidden in the subgraph",
            "optional / experimental",
            "## Why this layout is intentional\n\nThe visible **Director** owns rich Studio state, reference cards, and `@Image` editing. The reusable subgraph owns ordinary typed sampling and exact-frame decode sockets.\n\nKeeping that boundary avoids invisible promoted widgets and makes the main path readable.",
            [170, -180],
            [520, 320],
            13,
        ),
        note(
            25,
            "Image reference semantics",
            "settings",
            "## Choose what each image contributes\n\n- `identity` / `character` + `fully_preserved`: keep the exact person or design.\n- `style` + `attribute_transfer`: borrow rendering language, not content.\n- `composition` / `layout`: borrow placement and hierarchy.\n- `outfit`, `pose`, `typography`, `lighting`, `texture`, `object`, and `environment`: narrow transfers.\n\n**Explicit card metadata always wins** over inference.",
            [1560, 260],
            [430, 390],
            15,
        ),
        note(
            26,
            "Sampling and frame extraction",
            "models",
            "## Profiles and decode\n\n- **Base Quality / Balanced:** native H3; no acceleration files.\n- **LightX v0.1:** Kijai's empirical four-step ComfyUI recipe.\n- **PDD 600 / 900:** four-step REF2VA students; requires references and Mamad8's node package.\n\nThe Director's **Decoder** control chooses the original H3 Video VAE or the fastest experimental T=1 Image VAE. Temporal quality controls 5/9/13/20-frame video packets. Current ComfyUI chunked H3 VAE I/O reduces memory with identical pixels; it is not advertised as a speed boost.",
            [1560, 700],
            [430, 310],
            16,
        ),
        note(
            27,
            "Benchmark Lab - quality and speed diagnosis",
            "optional / experimental",
            "## Compare two or many setups\n\n1. Enter Base, LightX, or PDD profiles and resolution targets.\n2. Check the exact generation count shown on the node.\n3. Turn **Benchmark ON** in the purple Run mode switch.\n\nNormal sampling stays lazy and is not scheduled. Same seed is the fairest comparison; new seeds are for diversity sweeps. Disable live cells for maximum throughput.",
            [820, 1660],
            [480, 400],
            17,
        ),
        note(
            28,
            "Model downloads · RECOMMENDED core",
            "models",
            "## RECOMMENDED · proven L4 core · ~50.4 GB / 47.0 GiB\n\nDownload each file directly into the shown `ComfyUI/models/` folder:\n\n- [Kijai FL2VA pruned W4A8 · 12.54 GB / 11.68 GiB](https://huggingface.co/Kijai/MiniMax-H3-experimental/resolve/main/minimax_h3_fl2va_pruned_w4a8_mixed.safetensors?download=true) → `diffusion_models/`\n- [Kijai REF2VA pruned W4A8 · 11.77 GB / 10.96 GiB](https://huggingface.co/Kijai/MiniMax-H3-experimental/resolve/main/minimax_h3_ref2va_pruned_w4a8_mixed.safetensors?download=true) → `diffusion_models/`\n- [H3 Qwen3-VL 32B NVFP4 · 15.7 GB](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors?download=true) → `text_encoders/`\n- [Original H3 Video VAE FP16 · 5.2 GB](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors?download=true) → `vae/`\n- [Qwen3-VL 4B analyzer + writer · 5.2 GB](https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors?download=true) → `text_encoders/`\n\n## Optional acceleration and previews\n\n- [TAEH3 live preview · 0.01 GB](https://huggingface.co/Kijai/MiniMax-H3-TAE/resolve/main/vae_approx/taeh3.safetensors?download=true) → `vae_approx/`\n- [LightX resized rank-21 · 0.31 GB](https://huggingface.co/Kijai/MiniMax-H3_comfy/resolve/main/loras/minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors?download=true) → `loras/`\n- [Experimental T=1 Image VAE · 5.2 GB](https://huggingface.co/Mamad8/MiniMax-H3-Image-VAE/resolve/main/minimax_h3_t1_image_vae_step1597.safetensors?download=true) → `vae/`\n- [Qwen3-VL 8B writer · 10.6 GB](https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_8b_fp8_scaled.safetensors?download=true) → `text_encoders/`\n\n## Optional PDD · choose 600 or 900 · ~1.30 GB each\n\n- [PDD 900 LoRA · 0.60 GB](https://huggingface.co/Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8/resolve/main/LORA_h3_pdd_af384_step900_s.safetensors?download=true) → `loras/`\n- [PDD 900 heads · 0.70 GB](https://huggingface.co/Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8/resolve/main/HEADS_h3_pdd_af384_step900_bank.safetensors?download=true) → `pdd_heads/`\n- [PDD 600 LoRA · 0.60 GB](https://huggingface.co/Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8/resolve/main/LORA_h3_pdd_af384_step600_s.safetensors?download=true) → `loras/`\n- [PDD 600 heads · 0.70 GB](https://huggingface.co/Mamad8/MiniMaxH3_R2V-PDD-Turbo-LoRA-Mamad8/resolve/main/HEADS_h3_pdd_af384_step600_bank.safetensors?download=true) → `pdd_heads/`\n- [Install the required PDD custom node](https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8)\n\n> [!NOTE]\n> Core + every optional file above is ~69.2 GB. H3 Studio never downloads models automatically.",
            [1560, 1080],
            [430, 720],
            18,
        ),
        note(
            29,
            "Upscaling, outpainting, and inpainting",
            "optional / experimental",
            "Upscaling is safest after H3's selected still: use ComfyUI's built-in Upscale Model Loader + Image Upscale With Model and a trusted image upscaler. H3 semantic outpainting works by increasing the target aspect ratio and explicitly placing the original reference within the new frame. Exact mask inpainting is not implemented here: H3 Studio has no verified mask-conditioned H3 route, and ComfyUI's VAE Encode for Inpainting requires a model trained for that contract. The node will not pretend semantic reference editing is pixel-locked inpainting.",
            [1560, 1860],
            [480, 390],
            19,
        ),
    ]
    groups = [
        {
            "id": 1,
            "title": "01 · DIRECT THE IMAGE",
            "bounding": [-1500, 160, 860, 940],
            "color": "#355b54",
            "font_size": 28,
            "flags": {},
        },
        {
            "id": 2,
            "title": "02 · MODELS AND CONDITIONING",
            "bounding": [-580, 190, 680, 600],
            "color": "#2f665b",
            "font_size": 26,
            "flags": {},
        },
        {
            "id": 3,
            "title": "03 · SAMPLE AND EXTRACT STILL",
            "bounding": [160, 190, 740, 1230],
            "color": "#6b5937",
            "font_size": 26,
            "flags": {},
        },
        {
            "id": 4,
            "title": "04 · OUTPUT",
            "bounding": [970, 190, 560, 1320],
            "color": "#496073",
            "font_size": 26,
            "flags": {},
        },
        {
            "id": 5,
            "title": "REFERENCE GUIDE",
            "bounding": [1500, 190, 540, 2300],
            "color": "#5c5243",
            "font_size": 24,
            "flags": {},
        },
        {
            "id": 6,
            "title": "READ BEFORE FIRST RUN",
            "bounding": [-1500, -240, 2750, 400],
            "color": "#324e49",
            "font_size": 30,
            "flags": {},
        },
        {
            "id": 7,
            "title": "OPTIONAL - MULTI-PROFILE BENCHMARK LAB",
            "bounding": [-580, 1600, 1940, 700],
            "color": "#60467a",
            "font_size": 28,
            "flags": {},
        },
    ]
    return {
        "id": WORKFLOW_ID,
        "revision": 0,
        "last_node_id": max(item["id"] for item in nodes),
        "last_link_id": links.next_id - 1,
        "nodes": nodes,
        "links": links.items,
        "groups": groups,
        "definitions": {"subgraphs": [build_subgraph()]},
        "config": {},
        "extra": {
            "ds": {"scale": 0.72, "offset": [1120, 330]},
            "frontendVersion": "1.30.0",
            "h3studio": {
                "schema_version": 8,
                "template_version": "1.6.0",
                "design_source": "H3 Studio maintained column layout",
                "audio_prompt_sections": False,
                "hub_included": False,
            },
        },
        "version": 0.4,
    }


def polish_release_workflow(workflow):
    if WORKFLOW_PATH.exists():
        return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    nodes = {item["id"]: item for item in workflow["nodes"]}
    groups = {item["id"]: item for item in workflow["groups"]}

    def place(node_id, pos, size):
        target = nodes[node_id]
        target["pos"] = list(pos)
        target["size"] = list(size)

    def rewrite_note(node_id, title, text, pos, size):
        target = nodes[node_id]
        target["title"] = title
        target["pos"] = list(pos)
        target["size"] = list(size)
        target["widgets_values"][1] = text

    # Main execution columns. Every group has an explicit gutter and every
    # contained node keeps at least 40 px of breathing room from group chrome.
    place(10, [-1450, 220], [720, 820])
    place(11, [-560, 260], [600, 240])
    place(12, [-560, 580], [600, 170])
    place(16, [180, 260], [700, 620])
    place(13, [180, 940], [700, 480])
    place(14, [1060, 260], [460, 420])
    place(15, [1060, 750], [460, 190])
    place(30, [1060, 1010], [460, 420])
    place(17, [-560, 1960], [820, 540])
    place(19, [340, 1960], [440, 190])

    rewrite_note(
        20,
        "START HERE · quick setup",
        "# Start here\n\n> **Fast path:** describe the final image, add only references that have a specific job, then queue.\n\n## Make an image\n\n1. Write naturally in the **Director**.\n2. Add references only when needed. They become ordered `@Image1`, `@Image2`, and so on.\n3. Choose role, retention, aspect ratio, resolution, and seed.\n4. Queue the workflow.\n\n*No references* uses FL2VA text-to-image. **Multiple references** use REF2VA.",
        [-1450, -190],
        [500, 350],
    )
    rewrite_note(
        21,
        "Prompt enhancement",
        "# Prompt enhancement\n\n> *Two separate Qwen stages are used only when you enable them.*\n\n## Image analysis\n\n- **Analyze image pixels:** Qwen3-VL creates factual source descriptions and can repair automatic roles.\n\n## Prompt writing\n\n- **Prompt enhancement:** a compact text-only pass turns the request plus reference facts into a production prompt.\n\n**Same as image analyzer** lets one loaded checkpoint perform both jobs. Choose a separate writer only when you intentionally want to stage another model.",
        [-910, -190],
        [520, 350],
    )
    rewrite_note(
        22,
        "Routing",
        "# Routing\n\n> **Auto is the recommended default.**\n\n- **0 references:** FL2VA text-to-image\n- **1 anchor:** FL2VA image editing when requested\n- **Multiple references:** REF2VA\n\n*Forced routes are diagnostic controls.* Invalid reference and route combinations are rejected before model work starts.",
        [-370, -190],
        [520, 350],
    )
    rewrite_note(
        24,
        "Why the Director stays visible",
        "# Why the Director stays visible\n\n> The **Director** owns rich Studio state, reference cards, and `@Image` editing.\n\nThe reusable sampling graph only owns ordinary typed sampling and decode sockets. Keeping that boundary visible avoids fragile promoted DOM widgets and keeps the main path readable.\n\n**UI state stays here.** *Sampling stays reusable.*",
        [170, -190],
        [520, 350],
    )
    rewrite_note(
        25,
        "Reference semantics",
        "# Reference semantics\n\n> **Explicit card metadata always wins** over automatic inference.\n\n## Common roles\n\n- **identity / character** + `fully_preserved`: keep the person or design\n- **style** + `attribute_transfer`: borrow rendering language, not content\n- **composition / layout:** borrow placement and hierarchy\n- **outfit, pose, typography, lighting, texture, object, environment:** narrow transfers\n\n*Give each reference one clear visual job whenever possible.*",
        [1700, 260],
        [500, 430],
    )
    rewrite_note(
        26,
        "Sampling profiles",
        "# Sampling profiles\n\n> Choose the profile in the **Director**. The sampling graph follows it automatically.\n\n- **Base Quality / Balanced:** native H3 with no acceleration file\n- **LightX v0.1:** four-step accelerated recipe\n- **PDD 600 / 900:** four-step REF2VA students and requires the PDD node package\n\n## Frame extraction\n\nThe temporal quality setting controls the H3 frame packet. The selector then returns the recommended still.\n\n*Decode tuning is documented beside the decode controls.*",
        [1700, 750],
        [500, 380],
    )
    rewrite_note(
        27,
        "Benchmark Lab",
        "# Benchmark Lab\n\n> **Optional:** use this only when comparing quality or speed.\n\n1. Enter sampling profiles and resolution targets.\n2. Check the exact generation count on the node.\n3. Turn **Benchmark ON** in the purple Run mode switch.\n\n**Same seed** is the fairest comparison. *New seeds* are better for diversity sweeps. Disable live cells when you only care about throughput.",
        [840, 1920],
        [500, 420],
    )
    rewrite_note(
        28,
        "Model downloads",
        "# Recommended model set\n\n> **Core setup:** download files directly into the shown `ComfyUI/models/` folders. H3 Studio never downloads model weights automatically.\n\n## Core\n\n- [Kijai FL2VA pruned W4A8](https://huggingface.co/Kijai/MiniMax-H3-experimental/resolve/main/minimax_h3_fl2va_pruned_w4a8_mixed.safetensors?download=true) → `diffusion_models/`\n- [Kijai REF2VA pruned W4A8](https://huggingface.co/Kijai/MiniMax-H3-experimental/resolve/main/minimax_h3_ref2va_pruned_w4a8_mixed.safetensors?download=true) → `diffusion_models/`\n- [H3 Qwen3-VL 32B NVFP4](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors?download=true) → `text_encoders/`\n- [Original H3 Video VAE FP16](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors?download=true) → `vae/`\n- [Qwen3-VL 4B analyzer + writer](https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors?download=true) → `text_encoders/`\n\n## Optional\n\n- [TAEH3 live preview](https://huggingface.co/Kijai/MiniMax-H3-TAE/resolve/main/vae_approx/taeh3.safetensors?download=true) → `vae_approx/`\n- [LightX resized rank-21](https://huggingface.co/Kijai/MiniMax-H3_comfy/resolve/main/loras/minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors?download=true) → `loras/`\n- [Experimental T=1 Image VAE](https://huggingface.co/Mamad8/MiniMax-H3-Image-VAE/resolve/main/minimax_h3_t1_image_vae_step1597.safetensors?download=true) → `vae/`\n- [Qwen3-VL 8B writer](https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_8b_fp8_scaled.safetensors?download=true) → `text_encoders/`\n\n## Optional PDD\n\nChoose either the **600** or **900** LoRA + heads pair and install [Mamad8's PDD custom node](https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8).",
        [1700, 1190],
        [500, 760],
    )
    rewrite_note(
        29,
        "Upscaling / outpainting / inpainting",
        "# Post-processing\n\n- **Upscaling:** run a normal ComfyUI image upscaler after the selected H3 still.\n- **Outpainting:** increase the target aspect ratio and explicitly place the original reference inside the new frame.\n- **Inpainting:** exact mask-conditioned H3 inpainting is **not implemented** here.\n\n> *Semantic reference editing is not pixel-locked inpainting, and H3 Studio does not present it as one.*",
        [1700, 2010],
        [500, 390],
    )

    decode_note = note(
        31,
        "Native H3 VAE decode",
        "models",
        "# Native H3 VAE decode\n\n> **Start with Auto.** It keeps the proven native `256 / 64` geometry and chooses tile batching from available VRAM.\n\n## Manual controls\n\n- **Tile size:** `256`, `320`, `384`, `512`\n- **Overlap:** `64`, `96`, `128`\n- **Tile batch:** `Auto`, `1`, `2`, `4`\n\n**Larger tiles** use more VRAM but reduce tile count. *Smaller tiles* are safer when memory is tight.\n\n> Change Manual values only when tuning or benchmarking. **Auto** is the compatibility default.",
        [180, 1480],
        [700, 320],
        20,
    )
    if 31 not in nodes:
        workflow["nodes"].append(decode_note)
        nodes[31] = decode_note

    groups[1]["bounding"] = [-1500, 160, 860, 1020]
    groups[2]["bounding"] = [-620, 190, 720, 660]
    groups[3]["bounding"] = [120, 190, 820, 1640]
    groups[4]["bounding"] = [1000, 190, 580, 1320]
    groups[5]["bounding"] = [1640, 190, 620, 2260]
    groups[6]["bounding"] = [-1500, -250, 2750, 410]
    groups[7]["bounding"] = [-620, 1880, 1980, 700]

    workflow["last_node_id"] = max(item["id"] for item in workflow["nodes"])
    workflow["extra"]["h3studio"]["template_version"] = "1.7.0"
    workflow["extra"]["h3studio"]["design_source"] = "H3 Studio release column layout with guarded gutters"
    return workflow



def encoded(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail when committed outputs differ from generated data.")
    args = parser.parse_args()
    workflow_text = encoded(polish_release_workflow(build_workflow()))
    subgraph_text = encoded(build_subgraph_blueprint())
    expected = [
        (WORKFLOW_PATH, workflow_text),
        (SUBGRAPH_PATH, subgraph_text),
    ]
    if args.check:
        stale = [
            str(path.relative_to(ROOT))
            for path, text in expected
            if not path.exists() or path.read_text(encoding="utf-8") != text
        ]
        if stale:
            raise SystemExit("Generated workflow outputs are stale: " + ", ".join(stale))
        print("Generated workflow outputs are current.")
        return
    for path, text in expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"Wrote {path.relative_to(ROOT)} ({text.count(chr(10)):,} lines)")


if __name__ == "__main__":
    main()
