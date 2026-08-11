import test from "node:test";
import assert from "node:assert/strict";

import { noteViewportHeight } from "../../web/js/core/note_layout.js";

test("workflow note viewport follows the restored serialized node height", () => {
  assert.equal(noteViewportHeight(320), 266);
  assert.equal(noteViewportHeight(560), 506);
});

test("workflow note viewport keeps a usable minimum before configuration", () => {
  assert.equal(noteViewportHeight(0), 246);
  assert.equal(noteViewportHeight(180), 160);
});
