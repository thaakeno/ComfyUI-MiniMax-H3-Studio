import test from "node:test";
import assert from "node:assert/strict";

import { benchmarkMatrixSummary, matrixTokens } from "../../web/js/core/benchmark_matrix.js";

test("benchmark count reflects profiles, resolutions and repeats", () => {
  const summary = benchmarkMatrixSummary({
    profiles: "base_quality_20, lightx_er_sde_4\nlightx_sa_solver_4",
    megapixels: "0.4, 1.0",
    repeats: 2,
    maxGenerations: 24,
  });
  assert.equal(summary.count, 12);
  assert.equal(summary.guarded, false);
  assert.equal(summary.valid, true);
});

test("benchmark count exposes guarded and invalid matrices before queue", () => {
  assert.equal(benchmarkMatrixSummary({ profiles: "base,lightx,pdd", megapixels: "0.4,1,2", repeats: 2, maxGenerations: 12 }).guarded, true);
  assert.equal(benchmarkMatrixSummary({ profiles: "base", megapixels: "not-a-number", repeats: 1 }).valid, false);
});

test("VAE comparison always reports its two decodes", () => {
  assert.equal(benchmarkMatrixSummary({ comparisonKind: "VAE decode - same T=1 latent" }).count, 2);
  assert.deepEqual(matrixTokens("base, lightx\npdd"), ["base", "lightx", "pdd"]);
});
