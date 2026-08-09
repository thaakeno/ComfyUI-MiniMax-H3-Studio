import assert from "node:assert/strict";
import test from "node:test";

import { rangeValueFromPointer } from "../../web/js/core/dom.js";

const OPTIONS = { min: 0.2, max: 2, step: 0.05 };
const RECT = { left: 100, width: 360 };

test("range pointer mapping respects the transformed viewport bounds", () => {
  assert.equal(rangeValueFromPointer(100, RECT, OPTIONS), 0.2);
  assert.equal(rangeValueFromPointer(280, RECT, OPTIONS), 1.1);
  assert.equal(rangeValueFromPointer(460, RECT, OPTIONS), 2);
});

test("range pointer mapping clamps beyond both visual edges", () => {
  assert.equal(rangeValueFromPointer(20, RECT, OPTIONS), 0.2);
  assert.equal(rangeValueFromPointer(700, RECT, OPTIONS), 2);
});
