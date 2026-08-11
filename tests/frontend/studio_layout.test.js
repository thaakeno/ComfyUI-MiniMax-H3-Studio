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

test("Studio panel desired size does not recursively depend on available width", () => {
  assert.deepEqual(studioPanelSize(900), [STUDIO_NODE_WIDTH, STUDIO_PANEL_HEIGHT]);
  assert.deepEqual(studioPanelSize(300), [STUDIO_NODE_WIDTH, STUDIO_PANEL_HEIGHT]);
});

test("Director cannot shrink below its maintained minimum size", () => {
  assert.deepEqual(clampStudioNodeSize([400, 600]), [STUDIO_NODE_WIDTH, STUDIO_NODE_HEIGHT]);
  assert.deepEqual(clampStudioNodeSize([760, 920]), [760, 920]);
});

test("initial Director normalization still resets runaway serialized height", () => {
  assert.deepEqual(initialStudioNodeSize([760, 4000]), [760, STUDIO_NODE_HEIGHT]);
});
