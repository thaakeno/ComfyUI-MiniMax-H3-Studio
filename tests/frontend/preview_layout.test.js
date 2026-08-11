import assert from "node:assert/strict";
import test from "node:test";

import { previewViewportHeight, previewWidgetSizing } from "../../web/js/core/preview_layout.js";

test("live preview fits below native controls in the maintained node", () => {
  assert.equal(previewViewportHeight(620), 430);
  assert.equal(previewViewportHeight(500), 310);
  assert.equal(previewViewportHeight(0), 430);
});

test("live preview gives Nodes 2.0 live DOM allocation callbacks", () => {
  const node = { size: [620, 620] };
  const sizing = previewWidgetSizing(node);
  assert.equal(sizing.getMinHeight(), 430);
  assert.equal(sizing.getMaxHeight(), 430);
  assert.equal(sizing.getHeight(), 430);

  node.size[1] = 700;
  assert.equal(sizing.getMinHeight(), 510);
});
