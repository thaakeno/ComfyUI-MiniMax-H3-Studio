import test from "node:test";
import assert from "node:assert/strict";

import { badgeSvg } from "../../telemetry/worker.js";

test("generation badge uses a compact image icon and GENERATED label", () => {
  const badge = badgeSvg(1280);
  assert.match(badge, /aria-label="images generated: 1\.3K"/);
  assert.match(badge, /<rect x="10" y="8" width="15" height="12"/);
  assert.match(badge, />GENERATED<\/text>/);
  assert.doesNotMatch(badge, />reported images<\/text>/i);
});
