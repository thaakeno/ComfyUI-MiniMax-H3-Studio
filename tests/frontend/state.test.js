import assert from "node:assert/strict";
import test from "node:test";

import {
  applyReferenceInferences,
  advanceSeedAfterGeneration,
  canonicalizeMentions,
  MAX_MEGAPIXELS,
  MAX_REFERENCES,
  MIN_MEGAPIXELS,
  UHD_4K_MEGAPIXELS,
  backendResolutionValue,
  capNativeForTarget,
  defaultState,
  formatMegapixels,
  missingReferenceOrdinals,
  normalizeState,
  parseState,
  planResolution,
  restorePersistedState,
  removeReferenceMentions,
  resolutionTier,
  rewriteMentions,
  serializeState,
  validateGenerationContract,
} from "../../web/js/core/state.js";

test("persisted state restores from the property backup when the hidden widget is corrupt", () => {
  const backup = serializeState(normalizeState({ prompt: "restored", ui: { advanced_open: true } }));
  const restored = restorePersistedState("{truncated", backup);
  assert.equal(restored.source, "property");
  assert.equal(restored.state.prompt, "restored");
  assert.equal(restored.state.ui.advanced_open, true);
  assert.ok(restored.error);
  assert.equal(restored.recovery, "{truncated");
});

test("unrecoverable persisted state reports the failure and preserves the raw value", () => {
  const restored = restorePersistedState("{truncated", "also invalid");
  assert.equal(restored.source, "default");
  assert.ok(restored.error);
  assert.equal(restored.recovery, "{truncated");
});
import {
  STUDIO_NODE_HEIGHT,
  STUDIO_PANEL_HEIGHT,
  initialStudioNodeSize,
  studioPanelSize,
} from "../../web/js/core/layout.js";
import {
  fullMediaUrl,
  parseStorageName,
  previewUrlForStorage,
  storageNameFromUpload,
} from "../../web/js/features/image_upload.js";

test("default state is an immediately usable text-to-image request", () => {
  const state = defaultState();
  assert.equal(state.schema_version, 10);
  assert.equal(state.generation.mode, "auto");
  assert.equal(state.generation.cap_native_resolution, false);
  assert.equal(state.generation.seed_locked, false);
  assert.equal(state.prompt_options.analyzer_resolution, 512);
  assert.deepEqual(state.references, []);
});

test("comparison presentation is opt-in and persists in Studio UI state", () => {
  assert.equal(defaultState().ui.comparison_enabled, false);
  const restored = normalizeState({ ui: { comparison_enabled: true } });
  assert.equal(restored.ui.comparison_enabled, true);
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
  state.prompt = "Keep @Image1's face";
  state.prompt_options.system_instruction = "Favor restrained editorial lighting.";
  state.references = [{
    filename: "face.png",
    role: "identity",
    retention: "fully_preserved",
    description: "The exact person",
    width: 1080,
    height: 1920,
    fingerprint: "blake2-person",
    thumbnail: "/h3studio/thumbnail?storage=face.png",
    tags: ["visually_analyzed", "role_origin:vision"],
    source_node_id: "42",
    source_slot: 0,
  }];
  const restored = parseState(serializeState(state));
  assert.equal(restored.prompt, state.prompt);
  assert.equal(restored.prompt_options.system_instruction, state.prompt_options.system_instruction);
  assert.equal(restored.references[0].filename, "face.png");
  assert.equal(restored.references[0].role, "identity");
  assert.equal(restored.references[0].retention, "fully_preserved");
  assert.deepEqual(
    {
      width: restored.references[0].width,
      height: restored.references[0].height,
      fingerprint: restored.references[0].fingerprint,
      thumbnail: restored.references[0].thumbnail,
      tags: restored.references[0].tags,
    },
    {
      width: 1080,
      height: 1920,
      fingerprint: "blake2-person",
      thumbnail: "/h3studio/thumbnail?storage=face.png",
      tags: ["visually_analyzed", "role_origin:vision"],
    },
  );
});

test("schema one settings migrate into their typed sections", () => {
  const state = normalizeState({
    schema_version: 1,
    settings: { mode: "reference_edit", megapixels: 1.4, enhance_mode: "vlm", adherence: 0.7 },
  });
  assert.equal(state.schema_version, 10);
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
  assert.equal(state.generation.megapixels, MAX_MEGAPIXELS);
  assert.equal(state.generation.seed, 0);
  assert.equal(state.prompt_options.adherence, 0);
  assert.equal(state.references.length, MAX_REFERENCES);
});

test("seed lock persists and controls post-generation advancement", () => {
  const locked = parseState(serializeState(normalizeState({ generation: { seed: 42, seed_locked: true } })));
  assert.equal(locked.generation.seed_locked, true);
  assert.equal(advanceSeedAfterGeneration(locked.generation, () => 99).seed, 42);

  const unlocked = normalizeState({ generation: { seed: 42, seed_locked: false } }).generation;
  assert.equal(advanceSeedAfterGeneration(unlocked, () => 99).seed, 99);
  assert.equal(advanceSeedAfterGeneration(unlocked, () => 42).seed, 43);
});

test("single-line prompt shaping survives state normalization", () => {
  const state = normalizeState({ prompt_options: { enhance_mode: "single_prompt" } });
  assert.equal(state.prompt_options.enhance_mode, "single_prompt");
  assert.equal(parseState(serializeState(state)).prompt_options.enhance_mode, "single_prompt");
});

test("generation validation rejects impossible requests before queueing", () => {
  assert.match(validateGenerationContract({ generation: { mode: "reference_edit" } }), /requires at least one/);
  assert.match(validateGenerationContract({
    generation: { mode: "auto", sampling_profile: "pdd_ref2va_4_900" },
  }), /PDD REF2VA requires/);
  assert.match(validateGenerationContract({
    generation: { mode: "reference_edit", route: "fl2va" },
    references: [{ filename: "face.png" }],
  }), /incompatible/);
});

test("generation validation accepts normal and PDD reference requests", () => {
  assert.equal(validateGenerationContract({ generation: { mode: "auto" } }), null);
  assert.equal(validateGenerationContract({
    generation: { mode: "auto", sampling_profile: "pdd_ref2va_4_900" },
    references: [{ filename: "face.png" }],
  }), null);
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

test("reference inference does not discard content identity or preview metadata", () => {
  const value = defaultState();
  value.references = [{
    filename: "source.png",
    role: "auto",
    role_auto: true,
    retention_auto: true,
    width: 720,
    height: 1280,
    fingerprint: "pixels-123",
    thumbnail: "/view?filename=source.png",
    tags: ["visually_analyzed"],
  }];
  const { state } = applyReferenceInferences(value, ["character"], ["fully_preserved"], ["Visible person"]);

  assert.equal(state.references[0].width, 720);
  assert.equal(state.references[0].height, 1280);
  assert.equal(state.references[0].fingerprint, "pixels-123");
  assert.equal(state.references[0].thumbnail, "/view?filename=source.png");
  assert.deepEqual(state.references[0].tags, ["visually_analyzed"]);
});

test("mention rewriting changes only actual friendly image references", () => {
  const source = "Use @Image 1, @image2, email x@Image3.test, and @@Image 4";
  const result = rewriteMentions(source, { 1: 3, 2: 1, 4: 2 });
  assert.equal(result, "Use @Image3, @Image1, email x@Image3.test, and @@Image 4");
});

test("legacy mention forms normalize to canonical compact tags", () => {
  assert.equal(canonicalizeMentions("Use @image 1, @IMAGE_2, and @Image3"), "Use @Image1, @Image2, and @Image3");
  assert.equal(normalizeState({ prompt: "Keep @Image 1" }).prompt, "Keep @Image1");
});

test("missing prompt references are identified and removable without touching valid mentions", () => {
  const state = normalizeState({
    prompt: "Keep @Image1, borrow light from @Image 2, and ignore x@Image3.test.",
    references: [{ filename: "connected.png" }],
  });
  assert.deepEqual(missingReferenceOrdinals(state), [2]);
  assert.equal(
    removeReferenceMentions(state.prompt, [2]),
    "Keep @Image1, borrow light from, and ignore x@Image3.test.",
  );
});

test("disabled cards remain missing until re-enabled", () => {
  const state = normalizeState({
    prompt: "Match @Image1 and @Image2",
    references: [{ filename: "one.png" }, { filename: "two.png", enabled: false }],
  });
  assert.deepEqual(missingReferenceOrdinals(state), [2]);
});

test("resolution planner keeps one and two megapixel requests distinct", () => {
  const one = planResolution("1:1", 1);
  const two = planResolution("1:1", 2);
  assert.deepEqual([one.width, one.height], [992, 992]);
  assert.deepEqual([two.width, two.height], [1408, 1408]);
  assert.equal(two.capped, false);
});

test("resolution planner reaches an aligned direct 4K-class canvas", () => {
  const plan = planResolution("16:9", UHD_4K_MEGAPIXELS);
  assert.deepEqual([plan.width, plan.height], [3840, 2176]);
  assert.equal(plan.capped, false);
});

test("megapixel display exposes stable minimum and maximum limits", () => {
  assert.equal(formatMegapixels(MIN_MEGAPIXELS), "0.20 MP");
  assert.equal(formatMegapixels(1), "1.00 MP");
  assert.equal(formatMegapixels(MAX_MEGAPIXELS), "8.50 MP");
});

test("targets above one megapixel automatically leave conservative mode", () => {
  assert.equal(capNativeForTarget(1, true), true);
  assert.equal(capNativeForTarget(1.05, true), false);
  assert.equal(capNativeForTarget(4, true), false);
  assert.equal(capNativeForTarget(0.4, false), false);
});

test("resolution tiers label safe and experimental direct ranges honestly", () => {
  assert.equal(resolutionTier(0.2).key, "fast");
  assert.equal(resolutionTier(1).key, "recommended");
  assert.equal(resolutionTier(2).key, "extended");
  assert.equal(resolutionTier(4).key, "experimental");
  assert.equal(resolutionTier(8.5).key, "extreme");
  assert.equal(resolutionTier(8.5, true).key, "conservative");
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

test("full image expansion removes preview transforms and resolves Studio thumbnails", () => {
  assert.equal(
    fullMediaUrl("/view?filename=source.png&type=input&subfolder=refs&preview=webp%3B90"),
    "/view?filename=source.png&type=input&subfolder=refs",
  );
  assert.equal(
    fullMediaUrl("/h3studio/thumbnail?storage=refs%2Fsource.png&size=112"),
    "/view?filename=source.png&subfolder=refs&type=input",
  );
});
