import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const guard = readFileSync(new URL("../../web/zz_h3studio_smart_benchmark_root_guard.js", import.meta.url), "utf8");
const benchmark = readFileSync(new URL("../../web/h3studio_smart_benchmark.js", import.meta.url), "utf8");

test("Smart Benchmark v7 redraws inside the original ComfyUI DOM root", () => {
  assert.match(benchmark, /root\.replaceChildren\(\.\.\.Array\.from\(next\.childNodes\)\)/);
  assert.doesNotMatch(benchmark, /__h3bRoot\.replaceWith/);
  assert.match(guard, /SmartBenchmarkStableRootGuardV7/);
  assert.match(guard, /duplicate DOM widget/);
});

test("Smart Benchmark remains bounded to one internal scroll surface", () => {
  assert.match(guard, /max-height", "560px"/);
  assert.match(guard, /overflow-y", "auto"/);
  assert.match(guard, /overflow-x", "hidden"/);
  assert.match(guard, /container-type:inline-size/);
  assert.match(guard, /ComfyUI owns the overlay's exact pixel width and canvas transform/);
  assert.match(guard, /root\.style\.removeProperty\("width"\)/);
  assert.match(benchmark, /const WIDGET_NAME = "h3studio_smart_benchmark"/);
  assert.match(benchmark, /hideOnZoom: true/);
});
