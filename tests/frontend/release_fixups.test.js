import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const preset = readFileSync(new URL("../../web/h3studio_release_fixups.js", import.meta.url), "utf8");
const benchmark = readFileSync(new URL("../../web/h3studio_smart_benchmark.js", import.meta.url), "utf8");
const migration = readFileSync(new URL("../../web/h3studio_smart_benchmark_legacy_migration.js", import.meta.url), "utf8");
const ui = readFileSync(new URL("../../web/zz_h3studio_ui_v4.js", import.meta.url), "utf8");
const pdd = readFileSync(new URL("../../web/h3studio_pdd_dependency.js", import.meta.url), "utf8");

test("shared presets resolve the Loader through the actual Director graph", () => {
  assert.match(preset, /inputComesFrom\(candidate, "studio_context", director\)/);
  assert.match(preset, /sourceForInput\(candidate, "h3_bundle"\)/);
  assert.match(preset, /fl2va_model/);
  assert.match(preset, /ref2va_model/);
  assert.match(preset, /custom_loras/);
  assert.match(preset, /runtime_optimization/);
  assert.match(preset, /__h3studioConfigured/);
});

test("Director add-ons remount after the core panel is rebuilt", () => {
  assert.match(preset, /MutationObserver/);
  assert.match(preset, /h3s-runtime-section/);
  assert.match(preset, /onConfigure/);
  assert.match(preset, /h3s-share-section/);
});

test("legacy benchmark absorbs into an existing Smart Benchmark instead of duplicating it", () => {
  assert.match(migration, /H3StudioABComparison/);
  assert.match(migration, /H3StudioSmartBenchmark/);
  assert.match(migration, /Existing Smart Benchmark found/);
  assert.match(migration, /instead of creating a duplicate/);
  assert.match(migration, /app\.graph\.remove\(oldNode\)/);
});

test("Smart Benchmark v7 owns one stable bounded renderer and comparisons update visible state immediately", () => {
  assert.match(benchmark, /max-height:560px/);
  assert.match(benchmark, /dedupeDomWidgets/);
  assert.match(benchmark, /h3studio_benchmark_preset/);
  assert.match(benchmark, /root\.replaceChildren/);
  assert.match(benchmark, /render\(node\)/);
  assert.match(benchmark, /Auto vs OG/);
  assert.match(benchmark, /\["runtime", "Runtime"\]/);
  assert.match(benchmark, /\["memory", "Memory"\]/);
  assert.match(benchmark, /Assets unavailable/);
  assert.match(benchmark, /\/h3studio\/assets/);
});

test("Director v7 force-hides leaked legacy widgets using zero-size hidden widgets", () => {
  assert.match(ui, /VISIBLE_NATIVE/);
  assert.match(ui, /item\.type = "hidden"/);
  assert.match(ui, /item\.computeSize = \(\) => \[0, 0\]/);
  assert.match(ui, /onDrawForeground/);
  assert.match(ui, /h3s-choice-menu/);
});

test("PDD dependency plus pair install/repair is one non-reentrant flow", () => {
  assert.match(pdd, /\/h3studio\/dependencies\/pdd\/install/);
  assert.match(pdd, /\/uad\/install/);
  assert.match(pdd, /\/uad\/verify-fast/);
  assert.match(pdd, /\[data-pdd-install\],\[data-pdd-repair\]/);
  assert.match(pdd, /stopImmediatePropagation/);
  assert.match(pdd, /node\.__h3PddPairFlowBusy/);
  assert.doesNotMatch(pdd, /button\.click\(\)/);
  assert.doesNotMatch(pdd, /window\.confirm/);
});
