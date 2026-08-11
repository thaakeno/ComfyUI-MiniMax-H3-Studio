import test from "node:test";
import assert from "node:assert/strict";

import { executedImageUrl, isNodeDownstream, selectOutputView } from "../../web/js/core/final_output.js";

test("final output reachability follows the actual workflow graph", () => {
  const links = {
    1: { origin_id: 10, target_id: 12 },
    2: { origin_id: 12, target_id: 19 },
    3: { origin_id: 19, target_id: 14 },
  };
  assert.equal(isNodeDownstream(links, 10, 14), true);
  assert.equal(isNodeDownstream(links, 10, 99), false);
});

test("executed output image uses the full ComfyUI media route", () => {
  const url = executedImageUrl({ filename: "final.png", subfolder: "H3Studio/day", type: "output" });
  assert.match(url, /^\/view\?/);
  assert.match(url, /filename=final.png/);
  assert.match(url, /subfolder=H3Studio%2Fday/);
  assert.match(url, /type=output/);
});

test("comparison output becomes the active Director view only when available", () => {
  assert.equal(selectOutputView("comparison", true, true), "comparison");
  assert.equal(selectOutputView("comparison", true, false), "result");
  assert.equal(selectOutputView("result", false, true), "comparison");
});
