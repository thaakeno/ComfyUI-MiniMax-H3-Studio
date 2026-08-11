import assert from "node:assert/strict";
import test from "node:test";

import { splitReferenceMentions } from "../../web/js/core/result_text.js";

test("structured and Qwen results expose canonical image mentions as pill parts", () => {
  assert.deepEqual(splitReferenceMentions("Use @Image 1 with @image_2."), [
    { type: "text", value: "Use " },
    { type: "mention", ordinal: 1, value: "@Image1" },
    { type: "text", value: " with " },
    { type: "mention", ordinal: 2, value: "@Image2" },
    { type: "text", value: "." },
  ]);
});
