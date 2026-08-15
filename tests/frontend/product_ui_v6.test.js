import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const ui = readFileSync(new URL("../../web/zz_h3studio_ui_v4.js", import.meta.url), "utf8");
const layout = readFileSync(new URL("../../web/js/core/layout.js", import.meta.url), "utf8");

test("Director v7 uses a stable primary workspace plus compact inspector", () => {
  assert.match(ui, /H3Studio\.NativeToolUIV7/);
  assert.match(ui, /h3s-v7-shell/);
  assert.match(ui, /h3s-v7-primary/);
  assert.match(ui, /h3s-v7-inspector/);
  assert.match(ui, /\["Direction", "Generated output", "References"\]/);
  assert.match(ui, /\["Generation", "Runtime", "Custom LoRAs", "Preset"\]/);
  assert.match(ui, /title\.textContent = "Preset"/);
  assert.match(ui, /button\.textContent = "Copy preset"/);
});

test("Director v7 mutation observer cannot retrigger itself while reparenting sections", () => {
  assert.match(ui, /observer\?\.disconnect\?\.\(\)/);
  assert.match(ui, /root\.__h3sDecorating = true/);
  assert.match(ui, /observer\?\.observe\?\.\(root, \{ childList: true \}\)/);
  assert.doesNotMatch(ui, /subtree:\s*true/);
});

test("Director node height is bounded instead of ratcheting upward forever", () => {
  assert.match(layout, /STUDIO_NODE_MAX_HEIGHT = 980/);
  assert.match(layout, /Math\.min\(STUDIO_NODE_MAX_HEIGHT/);
  assert.match(ui, /MAX_HEIGHT = 980/);
});

test("Director DOM widget remains zoom-aware and foreground work is throttled", () => {
  assert.match(ui, /widget\.options\.hideOnZoom = true/);
  assert.match(ui, /now - last < 140/);
  assert.match(ui, /MutationObserver/);
});
