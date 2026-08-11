export const STUDIO_PANEL_HEIGHT = 530;
export const STUDIO_NODE_WIDTH = 520;
export const STUDIO_NODE_HEIGHT = 780;

export function studioPanelSize() {
  // DOM-widget sizing is a desired-size callback, not an available-space
  // callback. Feeding Comfy's inner width back here causes node padding to be
  // subtracted again on every recompute, slowly shrinking the Director.
  return [STUDIO_NODE_WIDTH, STUDIO_PANEL_HEIGHT];
}

export function clampStudioNodeSize(size) {
  const width = Number(size?.[0]);
  const height = Number(size?.[1]);
  return [
    Math.max(STUDIO_NODE_WIDTH, Number.isFinite(width) ? width : 0),
    Math.max(STUDIO_NODE_HEIGHT, Number.isFinite(height) ? height : 0),
  ];
}

export function initialStudioNodeSize(size) {
  const width = Number(size?.[0]);
  return [Math.max(STUDIO_NODE_WIDTH, Number.isFinite(width) ? width : 0), STUDIO_NODE_HEIGHT];
}
