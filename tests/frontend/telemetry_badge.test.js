import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const readme = readFileSync(new URL("../../README.md", import.meta.url), "utf8");

test("generation badge reads the hosted GoatCounter aggregate", () => {
  assert.match(readme, /h3-studio\.goatcounter\.com%2Fcounter%2Fgenerated\.json/);
  assert.match(readme, /label=GENERATED/);
  assert.doesNotMatch(readme, /h3-studio-counter\.workers\.dev/);
  assert.doesNotMatch(readme, /telemetry\/worker\.js/);
});
