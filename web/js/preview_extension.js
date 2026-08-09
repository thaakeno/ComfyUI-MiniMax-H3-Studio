import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const TARGET = "H3StudioTAEH3Preview";

function installPreview(node) {
  if (node.__h3studioPreviewInstalled || typeof node.addDOMWidget !== "function") return;
  node.__h3studioPreviewInstalled = true;
  const root = document.createElement("div");
  root.className = "h3s-live-preview";
  const image = document.createElement("img");
  image.alt = "TAEH3 live sampling preview";
  const empty = document.createElement("div");
  empty.className = "h3s-live-preview-empty";
  empty.textContent = "Enable for fast approximate sampling previews";
  const status = document.createElement("div");
  status.className = "h3s-live-preview-status";
  root.append(image, empty, status);
  node.__h3studioPreviewElements = { image, empty, status };
  const widget = node.addDOMWidget("h3studio_live_preview", "h3studio_live_preview", root, {
    serialize: false,
    hideOnZoom: false,
  });
  widget.computeSize = (width) => [width, 230];
  node.setSize?.([Math.max(node.size?.[0] || 360, 360), Math.max(node.size?.[1] || 360, 360)]);
}

api.addEventListener("h3studio-preview", ({ detail }) => {
  const node = app.graph?.getNodeById?.(Number(detail?.node_id));
  const elements = node?.__h3studioPreviewElements;
  if (!elements || !detail?.image) return;
  elements.image.src = detail.image;
  elements.image.hidden = false;
  elements.empty.hidden = true;
  elements.status.textContent = `Step ${detail.step}/${detail.total} · ${detail.width} × ${detail.height}`;
  node.setDirtyCanvas?.(true, true);
});

app.registerExtension({
  name: "h3studio.taeh3-preview",
  async nodeCreated(node) {
    if (node.comfyClass === TARGET) installPreview(node);
  },
});
