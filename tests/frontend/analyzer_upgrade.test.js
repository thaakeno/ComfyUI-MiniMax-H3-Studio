import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const analyzer = readFileSync(new URL("../../h3studio/prompting/comfy_analyzer.py", import.meta.url), "utf8");
const runtimeWeb = readFileSync(new URL("../../h3studio/runtime_web.py", import.meta.url), "utf8");
const promptBenchmark = readFileSync(new URL("../../h3studio/nodes/prompt_prep_benchmark.py", import.meta.url), "utf8");
const benchmark = readFileSync(new URL("../../web/h3studio_smart_benchmark.js", import.meta.url), "utf8");

test("analyzer uses strict factual records and validates every reference ordinal", () => {
  assert.match(analyzer, /factual visual reference analyst/);
  assert.match(analyzer, /expected_ordinals/);
  assert.match(analyzer, /missing = sorted/);
  assert.match(analyzer, /word_count < 35/);
  assert.match(analyzer, /visually_analyzed/);
});

test("analyzer cache keys include image identity and source metadata", () => {
  assert.match(analyzer, /_analysis_cache_key/);
  assert.match(analyzer, /reference\.source_node_id/);
  assert.match(analyzer, /reference\.source_slot/);
  assert.match(analyzer, /reference\.filename/);
});

test("runtime diagnostics expose prompt-prep and conditioning residency truth", () => {
  assert.match(runtimeWeb, /prompt_prep/);
  assert.match(runtimeWeb, /text_encoder/);
  assert.match(runtimeWeb, /analyzer/);
  assert.match(runtimeWeb, /minicpm_status/);
  assert.match(runtimeWeb, /h3_conditioner/);
});

test("prompt prep benchmark measures end-to-end latency instead of only tokens per second", () => {
  assert.match(promptBenchmark, /cold_model_load_s/);
  assert.match(promptBenchmark, /warm_analyzer_s/);
  assert.match(promptBenchmark, /writer_s/);
  assert.match(promptBenchmark, /model_switch_s/);
  assert.match(promptBenchmark, /peak_vram_bytes/);
  assert.match(promptBenchmark, /peak_system_ram_bytes/);
  assert.match(promptBenchmark, /cache_hit_s/);
  assert.match(promptBenchmark, /analyzer_retries/);
  assert.match(promptBenchmark, /writer_retries/);
  assert.match(promptBenchmark, /single portrait/);
  assert.match(promptBenchmark, /text \/ OCR/);
});

test("smart benchmark v7 is one bounded native editor with understandable comparisons", () => {
  assert.match(benchmark, /max-height:560px/);
  assert.match(benchmark, /overflow:auto/);
  assert.match(benchmark, /dedupeDomWidgets/);
  assert.match(benchmark, /\["current", "Current"\]/);
  assert.match(benchmark, /\["auto-og", "Auto vs OG"\]/);
  assert.match(benchmark, /\["runtime", "Runtime"\]/);
  assert.match(benchmark, /\["memory", "Memory"\]/);
  assert.match(benchmark, /h3b7-scenario/);
  assert.match(benchmark, /h3b7-select/);
  assert.match(benchmark, /Assets unavailable/);
});
