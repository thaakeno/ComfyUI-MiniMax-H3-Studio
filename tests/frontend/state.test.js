import assert from "node:assert/strict";
import test from "node:test";

import {
  applyReferenceInferences,
  MAX_MEGAPIXELS,
  MAX_REFERENCES,
  MIN_MEGAPIXELS,
  backendResolutionValue,
  defaultState,
  formatMegapixels,
  normalizeState,
  parseState,
  planResolution,
  rewriteMentions,
  serializeState,
} from "../../web/js/core/state.js";
import {
  STUDIO_NODE_HEIGHT,
  STUDIO_PANEL_HEIGHT,
  initialStudioNodeSize,
  studioPanelSize,
} from "../../web/js/core/layout.js";
import { parseStorageName, previewUrlForStorage, storageNameFromUpload } from "../../web/js/features/image_upload.js";

test("default state is an immediately usable text-to-image request", () => {
  const state = defaultState();
  assert.equal(state.schema_version, 9);
  assert.equal(state.generation.mode, "auto");
  assert.equal(state.generation.cap_native_resolution, false);
  assert.equal(state.prompt_options.analyzer_resolution, 512);
  assert.deepEqual(state.references, []);
});

test("native analyzer resolution is preserved as the zero sentinel", () => {
  const state = normalizeState({ prompt_options: { analyzer_resolution: 0 } });
  assert.equal(state.prompt_options.analyzer_resolution, 0);
});

test("custom resolution uses the exact backend combo label", () => {
  assert.equal(backendResolutionValue("custom"), "Custom");
  assert.equal(backendResolutionValue("Custom"), "Custom");
  assert.equal(backendResolutionValue("768P"), "768P");
});

test("state round-trips without losing reference metadata", () => {
  const state = defaultState();
  state.prompt = "Keep @Image 1's face";
  state.references = [{
    filename: "face.png",
    role: "identity",
    retention: "fully_preserved",
    description: "The exact person",
    source_node_id: "42",
    source_slot: 0,
  }];
  const restored = parseState(serializeState(state));
  assert.equal(restored.prompt, state.prompt);
  assert.equal(restored.references[0].filename, "face.png");
  assert.equal(restored.references[0].role, "identity");
  assert.equal(restored.references[0].retention, "fully_preserved");
});

test("schema one settings migrate into their typed sections", () => {
  const state = normalizeState({
    schema_version: 1,
    settings: { mode: "reference_edit", megapixels: 1.4, enhance_mode: "vlm", adherence: 0.7 },
  });
  assert.equal(state.schema_version, 9);
  assert.equal(state.generation.mode, "reference_edit");
  assert.equal(state.generation.megapixels, 1.4);
  assert.equal(state.prompt_options.enhance_mode, "compile_only");
  assert.equal(state.prompt_options.analyze_images, true);
  assert.equal(state.prompt_options.adherence, 0.7);
  assert.equal("settings" in state, false);
});

test("normalization clamps fields and limits references", () => {
  const state = normalizeState({
    generation: { megapixels: 99, seed: -5 },
    prompt_options: { adherence: -2 },
    references: Array.from({ length: 20 }, (_, index) => ({ filename: `${index}.png` })),
  });
  assert.equal(state.generation.megapixels, 2);
  assert.equal(state.generation.seed, 0);
  assert.equal(state.prompt_options.adherence, 0);
  assert.equal(state.references.length, MAX_REFERENCES);
});

test("single-line prompt shaping survives state normalization", () => {
  const state = normalizeState({ prompt_options: { enhance_mode: "single_prompt" } });
  assert.equal(state.prompt_options.enhance_mode, "single_prompt");
  assert.equal(parseState(serializeState(state)).prompt_options.enhance_mode, "single_prompt");
});

test("prompt inference updates auto-managed role and retention but preserves manual choices", () => {
  const value = defaultState();
  value.references = [
    { filename: "auto.png", role: "auto", retention: "attribute_transfer", role_auto: true, retention_auto: true },
    { filename: "manual.png", role: "style", retention: "reference_only", role_auto: false, retention_auto: false },
  ];
  const { state, changes } = applyReferenceInferences(
    value,
    ["face", "identity"],
    ["fully_preserved", "fully_preserved"],
  );
  assert.equal(state.references[0].role, "face");
  assert.equal(state.references[0].retention, "fully_preserved");
  assert.deepEqual(changes[0], { role: "face", retention: "fully_preserved" });
  assert.equal(state.references[1].role, "style");
  assert.equal(state.references[1].retention, "reference_only");
});

test("mention rewriting changes only actual friendly image references", () => {
  const source = "Use @Image 1, @image2, email x@Image3.test, and @@Image 4";
  const result = rewriteMentions(source, { 1: 3, 2: 1, 4: 2 });
  assert.equal(result, "Use @Image 3, @Image 1, email x@Image3.test, and @@Image 4");
});

test("resolution planner keeps one and two megapixel requests distinct", () => {
  const one = planResolution("1:1", 1);
  const two = planResolution("1:1", 2);
  assert.deepEqual([one.width, one.height], [992, 992]);
  assert.deepEqual([two.width, two.height], [1408, 1408]);
  assert.equal(two.capped, false);
});

test("megapixel display exposes stable minimum and maximum limits", () => {
  assert.equal(formatMegapixels(MIN_MEGAPIXELS), "0.20 MP");
  assert.equal(formatMegapixels(1), "1.00 MP");
  assert.equal(formatMegapixels(MAX_MEGAPIXELS), "2.00 MP");
});

test("studio layout cannot feed total node height back into panel height", () => {
  assert.deepEqual(studioPanelSize(640), [640, STUDIO_PANEL_HEIGHT]);
  assert.deepEqual(studioPanelSize(640), studioPanelSize(640));
  assert.deepEqual(initialStudioNodeSize([700, 50000]), [700, STUDIO_NODE_HEIGHT]);
});

test("custom dimensions determine custom aspect while area follows megapixels", () => {
  const plan = planResolution("custom", 0.5, 1600, 900, false);
  assert.equal(plan.width % 32, 0);
  assert.equal(plan.height % 32, 0);
  assert.ok(Math.abs(plan.width / plan.height - 16 / 9) < 0.08);
  assert.ok(Math.abs(plan.actualMegapixels - 0.5) < 0.06);
});

test("uploaded ComfyUI storage names survive state normalization", () => {
  const state = normalizeState({
    schema_version: 4,
    references: [{ filename: "portrait.png", storage_name: "h3studio/portrait.png", ordinal: 1 }],
  });
  assert.equal(state.references[0].filename, "portrait.png");
  assert.equal(state.references[0].storage_name, "h3studio/portrait.png");
  assert.equal(parseState(serializeState(state)).references[0].storage_name, "h3studio/portrait.png");
});

test("upload responses produce loadable storage names and previews", () => {
  const storage = storageNameFromUpload({ name: "face.png", subfolder: "h3studio", type: "input" });
  assert.equal(storage, "h3studio/face.png");
  assert.deepEqual(parseStorageName(storage), { filename: "face.png", subfolder: "h3studio", type: "input" });
  const preview = previewUrlForStorage(storage);
  assert.match(preview, /^\/h3studio\/thumbnail\?/);
  assert.match(preview, /storage=h3studio%2Fface.png/);
  assert.match(preview, /size=112/);
});
