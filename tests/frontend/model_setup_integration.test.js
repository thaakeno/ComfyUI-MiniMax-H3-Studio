import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../../web/h3_model_setup.js", import.meta.url), "utf8");

test("maintained workflow gets the model setup node", () => {
  assert.match(source, /H3StudioModelSetup/);
  assert.match(source, /beforeConfigureGraph\(graphData\)/);
  assert.match(source, /\[-2350,220\]/);
});

test("model setup integrates with UAD analyze verify and install APIs", () => {
  assert.match(source, /\/uad\/status/);
  assert.match(source, /\/uad\/analyze/);
  assert.match(source, /\/uad\/verify/);
  assert.match(source, /\/uad\/install/);
  assert.match(source, /models\/\$\{asset\.destination\}\/\$\{asset\.filename\}/);
});

test("missing UAD uses ComfyUI Manager install endpoint with explicit confirmation", () => {
  assert.match(source, /\/customnode\/install\/git_url/);
  assert.match(source, /window\.confirm/);
  assert.match(source, /Restart ComfyUI/);
  assert.match(source, /press R or hard refresh/);
});

test("manifest includes H3 role-aware destinations and current LightX profiles", () => {
  assert.match(source, /minimax_h3_fl2va_pruned_w4a8_mixed\.safetensors/);
  assert.match(source, /qwen3vl_32b_minimax_h3_nvfp4_awq\.safetensors/);
  assert.match(source, /minimax_h3_fl2v_lightx2v_turbo_8step_v1\.0_resized_avg_rank_24_bf16\.safetensors/);
  assert.match(source, /minimax_h3_ref2v_lightx2v_turbo_4step_v0\.1_resized_avg_rank_20_bf16\.safetensors/);
  assert.match(source, /destination:"vae_approx"/);
});
