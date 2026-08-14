import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const preset = readFileSync(new URL("../../web/h3studio_release_fixups.js", import.meta.url), "utf8");
const benchmark = readFileSync(new URL("../../web/h3studio_smart_benchmark_v2.js", import.meta.url), "utf8");
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

test("legacy benchmark is replaced by Smart Benchmark without losing graph wiring", () => {
  assert.match(benchmark, /H3StudioABComparison/);
  assert.match(benchmark, /H3StudioSmartBenchmark/);
  assert.match(benchmark, /inputSource\(oldNode, "h3_bundle"\)/);
  assert.match(benchmark, /inputSource\(oldNode, "studio_context"\)/);
  assert.match(benchmark, /outputTargets\(oldNode, 0\)/);
  assert.match(benchmark, /Migrated legacy Benchmark Lab to Smart Benchmark Lab/);
});

test("Smart Benchmark v2 hides raw JSON widgets and constrains overflowing controls", () => {
  assert.match(benchmark, /hideNativeWidget\(node, "scenarios_json"\)/);
  assert.match(benchmark, /hideNativeWidget\(node, "max_scenarios"\)/);
  assert.match(benchmark, /max-width:100%!important/);
  assert.match(benchmark, /overflow:hidden!important/);
  assert.match(benchmark, /grid-template-columns:repeat\(3,minmax\(0,1fr\)\)/);
});

test("installing a PDD pair installs the fixed Mamad8 custom node first", () => {
  assert.match(pdd, /\/h3studio\/dependencies\/pdd\/install/);
  assert.match(pdd, /\[data-pdd-install\],\[data-pdd-repair\]/);
  assert.match(pdd, /stopImmediatePropagation/);
  assert.match(pdd, /button\.click\(\)/);
  assert.match(pdd, /PDD node installed · restart/);
});
