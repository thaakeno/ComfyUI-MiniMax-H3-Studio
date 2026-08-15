export const STUDIO_PANEL_HEIGHT = 640;
export const STUDIO_NODE_WIDTH = 680;
export const STUDIO_NODE_HEIGHT = 780;
export const STUDIO_NODE_MAX_HEIGHT = 980;

export function studioPanelSize(width) {
  const safeWidth = Number.isFinite(Number(width)) ? Number(width) : 0;
  return [safeWidth, STUDIO_PANEL_HEIGHT];
}

export function clampStudioNodeSize(size, minimumSize = [STUDIO_NODE_WIDTH, STUDIO_NODE_HEIGHT]) {
  const width = Number(size?.[0]);
  const height = Number(size?.[1]);
  const minimumWidth = Number(minimumSize?.[0]);
  const minimumHeight = Number(minimumSize?.[1]);
  const resolvedMinHeight = Math.max(
    STUDIO_NODE_HEIGHT,
    Number.isFinite(minimumHeight) ? Math.min(minimumHeight, STUDIO_NODE_MAX_HEIGHT) : 0,
  );
  return [
    Math.max(
      STUDIO_NODE_WIDTH,
      Number.isFinite(minimumWidth) ? minimumWidth : 0,
      Number.isFinite(width) ? width : 0,
    ),
    Math.max(
      resolvedMinHeight,
      Math.min(STUDIO_NODE_MAX_HEIGHT, Number.isFinite(height) ? height : STUDIO_NODE_HEIGHT),
    ),
  ];
}

export function initialStudioNodeSize(size) {
  const width = Number(size?.[0]);
  return [Math.max(STUDIO_NODE_WIDTH, Number.isFinite(width) ? width : 0), STUDIO_NODE_HEIGHT];
}
