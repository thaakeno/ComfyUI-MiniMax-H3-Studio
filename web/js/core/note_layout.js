const NOTE_NODE_CHROME = 54;
const NOTE_MIN_VIEWPORT = 160;
const NOTE_DEFAULT_NODE_HEIGHT = 300;

export function noteViewportHeight(nodeHeight) {
  const height = Number(nodeHeight);
  const resolved = Number.isFinite(height) && height > 0 ? height : NOTE_DEFAULT_NODE_HEIGHT;
  return Math.max(NOTE_MIN_VIEWPORT, Math.round(resolved) - NOTE_NODE_CHROME);
}
