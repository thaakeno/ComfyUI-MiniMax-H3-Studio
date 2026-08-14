import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../../web/h3_manager_onboarding.js", import.meta.url), "utf8");

test("Manager onboarding uses ComfyUI api.fetchApi and current registry queue", () => {
  assert.match(source, /api\.fetchApi\("\/customnode\/installed"\)/);
  assert.match(source, /\/customnode\/getlist\?mode=default&skip_update=true/);
  assert.match(source, /api\.fetchApi\("\/manager\/queue\/install"/);
  assert.match(source, /api\.fetchApi\("\/manager\/queue\/start"/);
  assert.match(source, /\/manager\/queue\/status/);
});

test("missing UAD gets native install confirmation and current Extensions wording", () => {
  assert.match(source, /title: "H3 Studio setup"/);
  assert.match(source, /Install it now with ComfyUI-Manager/);
  assert.match(source, /Manager is opened from the Extensions button/);
  assert.match(source, /Install UAD now/);
});

test("legacy serialized UAD graph nodes are removed from the maintained workflow", () => {
  assert.match(source, /LEGACY_UAD_NODE = "UniversalAssetDownloader"/);
  assert.match(source, /removeLegacyUadNodes\(graphData\)/);
  assert.match(source, /graphData\.nodes = nodes\.filter/);
  assert.match(source, /removedLinkIds/);
});

test("onboarding retries Manager startup instead of trusting the first probe", () => {
  assert.match(source, /attempt < 12/);
  assert.match(source, /await sleep\(750\)/);
  assert.match(source, /managerSnapshot\(\)/);
});
