import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const runtime = readFileSync(new URL("../../web/h3studio_runtime.js", import.meta.url), "utf8");
const share = readFileSync(new URL("../../web/h3studio_share.js", import.meta.url), "utf8");
const benchmark = readFileSync(new URL("../../web/h3studio_smart_benchmark.js", import.meta.url), "utf8");
const ui = readFileSync(new URL("../../web/zz_h3studio_ui_v4.js", import.meta.url), "utf8");
const extension = readFileSync(new URL("../../h3studio/extension.py", import.meta.url), "utf8");

test("Director runtime UI exposes explainable Auto, unchanged OG and focused Expert overrides", () => {
  assert.match(runtime, /\["auto", "Auto", "Best default"/);
  assert.match(runtime, /\["og_current", "OG", "No override"/);
  assert.match(runtime, /Packed tokens/);
  assert.match(runtime, /Why:/);
  assert.match(runtime, /runtime_optimization/);
  assert.match(runtime, /Expert overrides/);
  assert.match(runtime, /FFN chunking is no longer exposed here/);
  assert.match(runtime, /Attention backend/);
  assert.match(runtime, /Head chunking/);
});

test("portable preset sharing includes runtime assets and exact LoRA strengths without prompts", () => {
  assert.match(share, /const PREFIX = "H3S1:"/);
  assert.match(share, /const ZIP_PREFIX = "H3S1Z:"/);
  assert.match(share, /CompressionStream/);
  assert.match(share, /strength: Number\(item\?\.strength/);
  assert.match(share, /loaderAssets/);
  assert.match(share, /widgetChoices/);
  assert.doesNotMatch(share, /prompt: state\.prompt/);
  assert.match(share, /Prompts and reference images are never included/);
  assert.match(ui, /button\.textContent = "Copy preset"/);
  assert.match(ui, /button\.textContent = "Copy run config"/);
});

test("Smart Benchmark v7 uses compact native controls and only calls OG 'OG'", () => {
  assert.match(benchmark, /Smart Benchmark/);
  assert.match(benchmark, /Search installed H3 LoRA/);
  assert.match(benchmark, /Installed transformer/);
  assert.match(benchmark, /modelChoices\(route\)/);
  assert.match(benchmark, /\+ Scenario/);
  assert.match(benchmark, /Auto vs OG/);
  assert.match(benchmark, /\["og_current", "OG"/);
  assert.doesNotMatch(benchmark, /OG \/ Current/);
  assert.match(benchmark, /h3studio_benchmark_preset/);
  assert.match(benchmark, /const SHARE_PREFIX = "H3B1:"/);
  assert.match(benchmark, /const SHARE_ZIP_PREFIX = "H3B1Z:"/);
  assert.match(benchmark, /Copy preset/);
  assert.match(benchmark, /h3b7-select/);
  assert.match(benchmark, /details", "h3b7-scenario/);
});

test("Smart Benchmark backend is registered on the ComfyUI extension surface", () => {
  assert.match(extension, /SMART_BENCHMARK_NODE_CLASS_MAPPINGS/);
  assert.match(extension, /\*\*SMART_BENCHMARK_NODE_CLASS_MAPPINGS/);
  assert.match(extension, /SMART_BENCHMARK_NODE_DISPLAY_NAME_MAPPINGS/);
});
