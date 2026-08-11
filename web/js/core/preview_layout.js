const PREVIEW_NODE_CHROME = 190;
const PREVIEW_MIN_VIEWPORT = 240;
const PREVIEW_DEFAULT_NODE_HEIGHT = 620;

export function previewViewportHeight(nodeHeight) {
  const height = Number(nodeHeight);
  const resolved = Number.isFinite(height) && height > 0 ? height : PREVIEW_DEFAULT_NODE_HEIGHT;
  return Math.max(PREVIEW_MIN_VIEWPORT, Math.round(resolved) - PREVIEW_NODE_CHROME);
}

export function previewWidgetSizing(node) {
  const height = () => previewViewportHeight(node?.size?.[1]);
  return {
    getMinHeight: height,
    getMaxHeight: height,
    getHeight: height,
  };
}
