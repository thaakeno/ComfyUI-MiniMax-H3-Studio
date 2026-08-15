import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const ui = readFileSync(new URL("../../web/zz_h3studio_ui_v4.js", import.meta.url), "utf8");

test("Director v6 uses a work surface plus inspector instead of a vertical card wall", () => {
  assert.match(ui, /H3Studio\.ProductUIV6/);
  assert.match(ui, /h3s-v6-layout/);
  assert.match(ui, /h3s-v6-main/);
  assert.match(ui, /h3s-v6-inspector/);
  assert.match(ui, /\["generation", "runtime", "advanced", "loras"\]/);
  assert.match(ui, /Reference cards become rows, not cards/);
  assert.match(ui, /Runtime becomes a compact segmented inspector/);
});

test("Product UI never overrides Smart Benchmark overlay width or enables parent overflow", () => {
  assert.doesNotMatch(ui, /h3b4-parent-fix\{[^}]*overflow:visible/);
  assert.doesNotMatch(ui, /\.h3b4\{[^}]*width:100%\s*!important/);
  assert.doesNotMatch(ui, /\.h3b4\{[^}]*max-width:100%\s*!important/);
  assert.match(ui, /root\.style\.removeProperty\("width"\)/);
  assert.match(ui, /root\.style\.removeProperty\("max-width"\)/);
  assert.match(ui, /root\.style\.setProperty\("overflow-x", "hidden", "important"\)/);
  assert.match(ui, /ComfyUI canvas[\s\S]*own the overlay's exact pixel width and transform/);
});

test("Director DOM widget remains zoom-aware and avoids the old continuous repaint walk", () => {
  assert.match(ui, /widget\.options\.hideOnZoom = true/);
  assert.match(ui, /DRAW_INTERVAL_MS = 160/);
  assert.match(ui, /MutationObserver/);
});
