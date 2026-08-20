import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../../web/h3_model_setup.js", import.meta.url), "utf8");

test("maintained workflow gets the model setup node", () => {
  assert.match(source, /H3StudioModelSetup/);
  assert.match(source, /beforeConfigureGraph\(graphData\)/);
  assert.match(source, /\[-2380,220\]/);
});

test("model setup integrates with nonblocking UAD analyze verify and install APIs", () => {
  assert.match(source, /\/uad\/status/);
  assert.match(source, /\/uad\/analyze-fast/);
  assert.match(source, /\/uad\/verify-fast/);
  assert.match(source, /\/uad\/install/);
  assert.match(source, /Promise\.all/);
  assert.match(source, /models\/\$\{asset\.destination\}\/\$\{asset\.filename\}/);
});

test("missing UAD uses ComfyUI Manager install endpoint with explicit confirmation", () => {
  assert.match(source, /\/customnode\/install\/git_url/);
  assert.match(source, /window\.confirm/);
  assert.match(source, /Restart ComfyUI/);
  assert.match(source, /press R or hard refresh/);
});

test("core runtime and acceleration LoRAs are visibly separated", () => {
  assert.match(source, /group:"core"/);
  assert.match(source, /group:"accel-recommended"/);
  assert.match(source, /group:"accel-alternative"/);
  assert.match(source, /Core runtime/);
  assert.match(source, /No acceleration LoRAs live here/);
  assert.match(source, /kind:"LoRA"/);
});

test("manifest includes H3 role-aware destinations and current LightX profiles", () => {
  assert.match(source, /minimax_h3_fl2va_pruned_w4a8_mixed\.safetensors/);
  assert.match(source, /qwen3vl_32b_minimax_h3_nvfp4_awq\.safetensors/);
  assert.match(source, /minimax_h3_fl2v_lightx2v_turbo_8step_v1\.0_resized_avg_rank_24_bf16\.safetensors/);
  assert.match(source, /minimax_h3_ref2v_lightx2v_turbo_4step_v0\.1_resized_avg_rank_20_bf16\.safetensors/);
  assert.match(source, /destination:"vae_approx"/);
});

test("model setup exposes the Comfy-ready 500K single-frame VAE without replacing the legacy option", () => {
  assert.match(source, /minimax_h3_single_frame_500k_comfy\.safetensors/);
  assert.match(source, /Alissonerdx\/MiniMax-H3-Single-Frame-VAE-500K-Comfy/);
  assert.match(source, /Single-frame Image VAE 500K · Comfy/);
  assert.match(source, /minimax_h3_t1_image_vae_step1597\.safetensors/);
  assert.match(source, /Legacy T=1 Image VAE · Mamad8/);
  assert.match(source, /id:"t1vae500k"[\s\S]*recommended:false/);
});

test("Model Setup node computeSize is static to prevent runaway expansion while widget fills node height", () => {
  assert.match(source, /node\.computeSize\s*=\s*function h3ModelSetupComputeSize/);
  assert.match(source, /widget\.computeSize\s*=\s*\(width\)\s*=>/);
  assert.match(source, /node\.onResize\s*=\s*function h3ModelSetupOnResize/);
});

test("Model Setup dynamically adapts widget viewport height to node height without empty space", () => {
  assert.match(source, /function modelSetupViewportHeight\(nodeHeight\)/);
  assert.match(source, /function modelSetupWidgetSizing\(node\)/);
  assert.match(source, /\.\.\.modelSetupWidgetSizing\(node\)/);
});

test("Model Setup renders full model groups and Hugging Face links even when UAD is missing", () => {
  const uadBlock = source.slice(source.indexOf("if (!uadReady)"), source.indexOf("body += `<div class=\"h3ms-actions\">"));
  assert.ok(!uadBlock.includes("return;"), "UAD block must not return early");
  assert.match(source, /for\s*\(const group of GROUPS\)/);
});

test("Model Setup checkbox toggles update selection in place without rebuilding DOM or resetting scroll", () => {
  assert.match(source, /const updateSelectedStats = \(\) =>/);
  assert.match(source, /root\.querySelectorAll\('\[data-select\]'\)\.forEach\(input=>input\.addEventListener\('change',\(\)=>\{[\s\S]*updateSelectedStats\(\);/);
  assert.match(source, /root\.scrollTop\s*=\s*prevScrollTop/);
});
