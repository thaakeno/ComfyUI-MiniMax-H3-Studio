import { app } from "../../../scripts/app.js";

import { clampStudioNodeSize } from "./core/layout.js";

const TARGET = "H3StudioDirector";

function preferredSize(node) {
  return node?.__h3studioPreferredSize || clampStudioNodeSize(node?.size);
}

function clampDirectorSize(node) {
  if (!node) return;
  const [width, height] = clampStudioNodeSize(node.size, preferredSize(node));
  if (!Array.isArray(node.size)) node.size = [width, height];
  else {
    node.size[0] = width;
    node.size[1] = height;
  }

  // Studio hides the large native widget set. Hidden widgets must contribute
  // exactly zero layout size; negative heights accumulate during Comfy size
  // recomputation and gradually shrink the Director.
  for (const target of node.widgets || []) {
    if (target?.__h3studioHidden) target.computeSize = () => [0, 0];
  }
}

function installSizeGuard(node) {
  if (!node || node.__h3studioSizeGuardInstalled) return;
  node.__h3studioSizeGuardInstalled = true;
  node.__h3studioPreferredSize = clampStudioNodeSize(node.size);

  const originalResize = node.onResize;
  node.onResize = function h3studioGuardedResize(size) {
    // LiteGraph exposes resizing_node only during an actual pointer resize.
    // Accept those dimensions as the user's new preferred size; automatic
    // computeSize/layout passes are not allowed to ratchet the node smaller.
    if (app.canvas?.resizing_node === this) {
      this.__h3studioPreferredSize = clampStudioNodeSize(size || this.size);
    }
    const result = originalResize?.apply(this, arguments);
    clampDirectorSize(this);
    return result;
  };

  // The main Studio extension reapplies hidden-widget sizing from its draw
  // hook, so normalize those widgets immediately afterwards on every draw.
  const originalDrawForeground = node.onDrawForeground;
  node.onDrawForeground = function h3studioGuardedDrawForeground() {
    const result = originalDrawForeground?.apply(this, arguments);
    clampDirectorSize(this);
    return result;
  };

  clampDirectorSize(node);
}

app.registerExtension({
  name: "H3Studio.DirectorSizeGuard",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== TARGET) return;
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function h3studioSizeGuardCreated() {
      const result = originalCreated?.apply(this, arguments);
      // Studio installs its DOM panel in a microtask. A timer runs afterwards,
      // so this guard wraps the final resize/draw hooks regardless of extension
      // registration order.
      setTimeout(() => installSizeGuard(this), 0);
      return result;
    };
  },
});
