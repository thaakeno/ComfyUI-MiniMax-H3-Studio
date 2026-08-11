export function matrixTokens(value) {
  return String(value || "")
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function benchmarkMatrixSummary({ comparisonKind, profiles, megapixels, repeats, maxGenerations }) {
  if (String(comparisonKind || "").startsWith("VAE decode")) {
    return { count: 2, profileCount: 1, resolutionCount: 1, valid: true, guarded: false };
  }
  const profileCount = new Set(matrixTokens(profiles)).size;
  const resolutionValues = matrixTokens(megapixels).map((value) => Number.parseFloat(value));
  const validResolutions = resolutionValues.filter((value) => Number.isFinite(value) && value >= 0.2 && value <= 8.5);
  const resolutionCount = new Set(validResolutions).size;
  const repeatCount = Math.max(1, Math.min(16, Number.parseInt(repeats, 10) || 1));
  const count = profileCount * resolutionCount * repeatCount;
  const valid = profileCount > 0 && resolutionCount > 0 && validResolutions.length === resolutionValues.length;
  const guard = Math.max(1, Math.min(128, Number.parseInt(maxGenerations, 10) || 24));
  return { count, profileCount, resolutionCount, valid, guarded: count > guard };
}
