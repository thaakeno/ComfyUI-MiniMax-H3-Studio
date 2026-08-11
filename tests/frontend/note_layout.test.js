import test from "node:test";
import assert from "node:assert/strict";

import { noteViewportHeight, noteWidgetSizing } from "../../web/js/core/note_layout.js";

test("workflow note viewport follows the restored serialized node height", () => {
  assert.equal(noteViewportHeight(320), 266);
  assert.equal(noteViewportHeight(560), 506);
});

test("workflow note viewport keeps a usable minimum before configuration", () => {
  assert.equal(noteViewportHeight(0), 246);
  assert.equal(noteViewportHeight(180), 160);
});

test("workflow note gives Nodes 2.0 live DOM allocation callbacks", () => {
  const node = { size: [520, 320] };
  const sizing = noteWidgetSizing(node);
  assert.equal(sizing.getMinHeight(), 266);
  assert.equal(sizing.getMaxHeight(), 266);
  assert.equal(sizing.getHeight(), 266);

  node.size[1] = 560;
  assert.equal(sizing.getMinHeight(), 506);
});
