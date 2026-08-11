import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../../web/js/preview_extension.js", import.meta.url), "utf8");

test("preview websocket handler calls the stored render function", () => {
  assert.equal(source.includes("elements.state.render()"), false);
  assert.equal((source.match(/elements\.render\(\)/g) || []).length >= 3, true);
});

test("preview websocket handler resolves qualified subgraph execution ids", () => {
  assert.equal(source.includes("function findNodeByQualifiedId"), true);
  assert.equal(source.includes('String(qid).split(":")'), true);
  assert.equal(source.includes("parentNode?.subgraph"), true);
  assert.equal(source.includes("findNodeByQualifiedId(app.graph, detail?.node_id)"), true);
});
