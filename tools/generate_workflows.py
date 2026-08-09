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
        "compile_only",
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
        "state": {"lastGroupid": 0, "lastNodeId": 106, "lastLinkId": 17, "lastRerouteId": 0},
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
    }


def build_workflow():
    links = Links()
    state = {
        "schema_version": 4,
        "prompt": "Describe the final still image.",
        "references": [],
        "prompt_options": {
            "enhance_mode": "compile_only",
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
    l_model_preview = links.add(12, 0, 16, 0, "MODEL")
    l_preview_sub = links.add(16, 0, 13, 0, "MODEL")
    l_positive_sub = links.add(12, 2, 13, 1, "CONDITIONING")
    l_latent_sub = links.add(12, 3, 13, 2, "LATENT")
    l_vae_sub = links.add(12, 4, 13, 3, "VAE")
    l_seed_sub = links.add(10, 5, 13, 4, "INT")
    l_context_sub = links.add(10, 0, 13, 5, "H3_STUDIO_CONTEXT")
    l_image_preview = links.add(13, 0, 14, 0, "IMAGE")
    l_image_save = links.add(13, 0, 15, 0, "IMAGE")

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
                output("studio_context", "H3_STUDIO_CONTEXT", [l_context_condition, l_context_sub]),
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
            [560, 180],
            order=1,
            inputs=[
                socket("fl2va_model", "COMBO", widget="fl2va_model"),
                socket("ref2va_model", "COMBO", widget="ref2va_model"),
                socket("text_encoder", "COMBO", widget="text_encoder"),
                socket("video_vae", "COMBO", widget="video_vae"),
            ],
            outputs=[
                output("h3_bundle", "H3_STUDIO_BUNDLE", [l_bundle_condition]),
                output("clip", "CLIP", None),
                output("video_vae", "VAE", None),
                output("model_info", "STRING", None),
            ],
            widgets=[
                "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors",
                "minimax_h3_ref2va_pruned_w4a8_mixed.safetensors",
                "qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
                "minimax_h3_video_vae_int8_convrot.safetensors",
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
            [620, 360],
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
            widgets=[False, "taeh3.safetensors", 512, 80, 1],
            color="#31475c",
            bgcolor="#202e3c",
        ),
        node(
            13,
            SUBGRAPH_ID,
            "H3 Studio · Sampling + exact still",
            [220, 700],
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
                output("image", "IMAGE", [l_image_preview, l_image_save]),
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
            inputs=[socket("images", "IMAGE", l_image_preview)],
            outputs=[],
            widgets=[],
            color="#3c514c",
            bgcolor="#24312f",
        ),
        node(
            15,
            "SaveImage",
            "Final still · save",
            [1030, 750],
            [440, 190],
            order=5,
            inputs=[
                socket("images", "IMAGE", l_image_save),
                socket("filename_prefix", "STRING", widget="filename_prefix"),
            ],
            outputs=[],
            widgets=["H3Studio/%date:yyyy-MM-dd%/H3_%seed%"],
            color="#3c514c",
            bgcolor="#24312f",
        ),
        note(
            20,
            "START HERE · three-minute setup",
            "quick start",
            "1. Write naturally in the Director.\n2. For references, click Add images inside the Director; each upload becomes an ordered @Image card.\n3. Set each image's role and retention policy, then type @ in the prompt to insert it.\n4. Choose aspect ratio, megapixels, and seed.\n5. Queue. Auto uses FL2VA for pure text and REF2VA for multi-reference work.\n\nThe workflow opens at 0/9 with no required files and runs text-to-image immediately.",
            [-1450, -180],
            [500, 320],
            10,
        ),
        note(
            21,
            "Prompt enhancement · what actually happens",
            "settings",
            "Production brief compiles deterministic sections: subject_definitions, summary, retention_analysis, and detailed_description. VLM analysis is optional and requires an explicitly selected local instruction-capable vision-language model. The Qwen3-VL ConvRot encoder loaded for H3 conditioning is not silently repurposed as a text generator. No model is downloaded automatically.",
            [-910, -180],
            [520, 320],
            11,
        ),
        note(
            22,
            "Routing · deliberate defaults",
            "settings",
            "Auto route keeps both proven paths available. Zero references selects FL2VA text-to-image. One reference may use FL2VA as an image anchor depending on requested mode. Multi-reference work selects REF2VA. Forced routes are advanced controls and diagnostics state when images are ignored or a route is experimental. REF2VA-only text-to-image remains unproven and is not the default.",
            [-370, -180],
            [520, 320],
            12,
        ),
        note(
            23,
            "Lightning.ai validation boundary",
            "troubleshooting",
            "This repository is checked locally for Python/JavaScript syntax, state migration, prompt compilation, resolution math, route decisions, node registration, and workflow graph integrity. Actual CUDA generation, model filenames, VRAM behavior, visual quality, and your installed ComfyUI frontend build must be smoke-tested in the Lightning workspace. Follow docs/LIGHTNING_TEST_PLAN.md before calling a GPU path verified.",
            [170, -180],
            [520, 320],
            13,
        ),
        note(
            24,
            "Why the Director is not hidden in the subgraph",
            "optional / experimental",
            "ComfyUI can promote native scalar widgets through subgraphs, but custom DOM controls and mention editors are not reliably promoted. The visible Director is therefore the stable product UI. Sampling and exact-frame decode live in the reusable subgraph because those are ordinary typed sockets. This preserves the polished @ tagging interface without repeating the old invisible-widget failure.",
            [710, -180],
            [520, 320],
            14,
        ),
        note(
            25,
            "Image reference semantics",
            "settings",
            "identity or character + fully_preserved: keep the exact person or design.\nstyle + attribute_transfer: borrow rendering language without copying content.\ncomposition or layout + attribute_transfer: borrow placement and hierarchy.\noutfit, pose, typography, lighting, texture, object, and environment provide narrower controls.\n\nThe compiler can infer roles from nearby prompt text, but explicit card metadata wins.",
            [1560, 260],
            [430, 390],
            15,
        ),
        note(
            26,
            "Sampling and frame extraction",
            "models",
            "H3 emits a short temporal latent even when the desired output is one image. The bundled subgraph samples that packet, decodes the exact requested profile, and selects the decoder-recommended stable frame. Base Quality needs no acceleration files. LightX profiles expect their matching LoRA upstream. Mamad8 PDD profiles are REF2VA-only and automatically pair the selected 600/900 student LoRA with its heads bank through the separately installed Mamad8 node package.",
            [1560, 700],
            [430, 310],
            16,
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
            "bounding": [160, 280, 740, 570],
            "color": "#6b5937",
            "font_size": 26,
            "flags": {},
        },
        {
            "id": 4,
            "title": "04 · OUTPUT",
            "bounding": [970, 190, 560, 820],
            "color": "#496073",
            "font_size": 26,
            "flags": {},
        },
        {
            "id": 5,
            "title": "REFERENCE GUIDE",
            "bounding": [1500, 190, 530, 880],
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
                "schema_version": 4,
                "template_version": "1.2.0",
                "design_source": "Alier v1.3.7 geometry",
                "audio_prompt_sections": False,
                "hub_included": False,
            },
        },
        "version": 0.4,
    }


def encoded(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail when committed outputs differ from generated data.")
    args = parser.parse_args()
    workflow_text = encoded(build_workflow())
    subgraph_text = encoded(build_subgraph())
    expected = [(WORKFLOW_PATH, workflow_text), (SUBGRAPH_PATH, subgraph_text)]
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
