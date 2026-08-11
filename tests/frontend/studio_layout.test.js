import assert from "node:assert/strict";
import test from "node:test";

import {
  STUDIO_NODE_HEIGHT,
  STUDIO_NODE_WIDTH,
  STUDIO_PANEL_HEIGHT,
  clampStudioNodeSize,
  initialStudioNodeSize,
  studioPanelSize,
} from "../../web/js/core/layout.js";

test("Studio panel height stays fixed while width follows Comfy allocation", () => {
  assert.deepEqual(studioPanelSize(900), [900, STUDIO_PANEL_HEIGHT]);
  assert.deepEqual(studioPanelSize(300), [300, STUDIO_PANEL_HEIGHT]);
});

test("Director cannot shrink below its maintained minimum size", () => {
  assert.deepEqual(clampStudioNodeSize([400, 600]), [STUDIO_NODE_WIDTH, STUDIO_NODE_HEIGHT]);
  assert.deepEqual(clampStudioNodeSize([760, 920]), [760, 920]);
});

test("Director preserves a previously accepted user size during automatic recompute", () => {
  assert.deepEqual(clampStudioNodeSize([620, 700], [760, 920]), [760, 920]);
  assert.deepEqual(clampStudioNodeSize([900, 1000], [760, 920]), [900, 1000]);
});

test("initial Director normalization still resets runaway serialized height", () => {
  assert.deepEqual(initialStudioNodeSize([760, 4000]), [760, STUDIO_NODE_HEIGHT]);
});
