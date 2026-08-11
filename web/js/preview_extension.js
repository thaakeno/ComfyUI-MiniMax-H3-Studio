import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { openImageLightbox } from "./core/lightbox.js";
import { previewViewportHeight, previewWidgetSizing } from "./core/preview_layout.js";

const TARGET = "H3StudioTAEH3Preview";
const MAX_HISTORY = 40;

function findNodeByQualifiedId(rootGraph, qid) {
  if (!rootGraph || qid == null) return null;
  const parts = String(qid).split(":");
  let graph = rootGraph;
  for (let index = 0; index < parts.length - 1; index += 1) {
    const parentId = Number.parseInt(parts[index], 10);
    if (!Number.isFinite(parentId)) return null;
    const parentNode = graph?.getNodeById?.(parentId);
    if (!parentNode?.subgraph) return null;
    graph = parentNode.subgraph;
  }
  const leafId = Number.parseInt(parts[parts.length - 1], 10);
  if (!Number.isFinite(leafId)) return null;
  return graph?.getNodeById?.(leafId) || null;
}

function installPreview(node) {
  if (node.__h3studioPreviewInstalled || typeof node.addDOMWidget !== "function") return;
  node.__h3studioPreviewInstalled = true;
  const labels = {
    enabled: "Live previews",
    tiny_vae: "Preview decoder",
    max_resolution: "Preview resolution",
    jpeg_quality: "Preview clarity",
    preview_every_n_steps: "Update every N steps",
  };
  for (const control of node.widgets || []) {
    if (labels[control.name]) control.label = labels[control.name];
  }
  const root = document.createElement("div");
  root.className = "h3s-live-preview";
  const images = [document.createElement("img"), document.createElement("img")];
  for (const image of images) {
    image.alt = "TAEH3 live sampling preview";
    image.title = "Click to expand";
    image.className = "h3s-live-preview-frame";
  }
  const empty = document.createElement("div");
  empty.className = "h3s-live-preview-empty";
  empty.textContent = "Enable for fast approximate sampling previews";
  const status = document.createElement("div");
  status.className = "h3s-live-preview-status";
  const navigation = document.createElement("div");
  navigation.className = "h3s-live-preview-navigation";
  const previous = document.createElement("button");
  previous.type = "button";
  previous.className = "h3s-live-preview-button";
  previous.textContent = "‹";
  previous.title = "Previous sampling preview";
  const position = document.createElement("span");
  position.className = "h3s-live-preview-position";
  const next = document.createElement("button");
  next.type = "button";
  next.className = "h3s-live-preview-button";
  next.textContent = "›";
  next.title = "Next sampling preview";
  navigation.append(previous, position, next);
  root.append(...images, empty, navigation, status);

  const state = {
    history: [], index: -1, runId: null, activeRunId: null, total: 0, visibleImage: -1, renderToken: 0,
  };
  const render = () => {
    const frame = state.history[state.index];
    if (!frame) {
      for (const image of images) {
        image.removeAttribute("src");
        image.classList.remove("is-visible");
      }
      state.visibleImage = -1;
      empty.hidden = false;
      empty.textContent = state.activeRunId
        ? "Sampling started · waiting for the first TAEH3 frame"
        : "Enable for fast approximate sampling previews";
      status.textContent = state.activeRunId && state.total ? `Step 0/${state.total}` : "";
      position.textContent = "";
      navigation.hidden = true;
      node.setDirtyCanvas?.(true, true);
      return;
    }
    empty.hidden = true;
    const elapsed = Number(frame.elapsed_seconds) || 0;
    const average = Number(frame.average_step_seconds) || 0;
    const eta = Number(frame.eta_seconds) || 0;
    status.textContent = `Step ${frame.step}/${frame.total} · ${frame.width} × ${frame.height} · ${elapsed.toFixed(1)}s · ${average.toFixed(2)}s/step${frame.step < frame.total ? ` · ETA ≈ ${eta.toFixed(1)}s` : ""}`;
    position.textContent = `${state.index + 1} / ${state.history.length}`;
    previous.disabled = state.index <= 0;
    next.disabled = state.index >= state.history.length - 1;
    navigation.hidden = state.history.length < 2;
    const token = ++state.renderToken;
    const targetIndex = state.visibleImage === 0 ? 1 : 0;
    const target = images[targetIndex];
    target.onload = () => {
      if (token !== state.renderToken) return;
      images.forEach((candidate, index) => candidate.classList.toggle("is-visible", index === targetIndex));
      state.visibleImage = targetIndex;
    };
    target.src = frame.image;
    if (target.complete) target.onload();
    node.setDirtyCanvas?.(true, true);
  };
  previous.addEventListener("click", (event) => {
    event.stopPropagation();
    state.index = Math.max(0, state.index - 1);
    render();
  });
  next.addEventListener("click", (event) => {
    event.stopPropagation();
    state.index = Math.min(state.history.length - 1, state.index + 1);
    render();
  });
  for (const image of images) {
    image.addEventListener("click", (event) => {
      event.stopPropagation();
      const frame = state.history[state.index];
      openImageLightbox(frame?.image, status.textContent || "Expanded TAEH3 sampling preview");
    });
  }
  navigation.hidden = true;
  node.__h3studioPreviewElements = { state, render, root, empty };
  const widget = node.addDOMWidget("h3studio_live_preview", "h3studio_live_preview", root, {
    serialize: false,
    hideOnZoom: false,
    ...previewWidgetSizing(node),
  });
  widget.computeSize = (width) => [width, previewViewportHeight(node.size?.[1])];
  node.setSize?.([Math.max(node.size?.[0] || 460, 460), Math.max(node.size?.[1] || 620, 620)]);
}

api.addEventListener("h3studio-preview", ({ detail }) => {
  const node = findNodeByQualifiedId(app.graph, detail?.node_id);
  const elements = node?.__h3studioPreviewElements;
  if (!elements) return;
  const runId = String(detail.run_id || "");
  if (detail?.error) {
    elements.state.activeRunId = runId;
    elements.state.history = [];
    elements.state.index = -1;
    elements.render();
    elements.empty.textContent = `Preview unavailable: ${detail.error}`;
    return;
  }
  if (detail?.reset) {
    elements.state.history = [];
    elements.state.index = -1;
    elements.state.runId = runId;
    elements.state.activeRunId = runId;
    elements.state.total = Number(detail.total) || 0;
    elements.render();
    return;
  }
  if (!detail?.image || (elements.state.activeRunId && elements.state.activeRunId !== runId)) return;
  if (elements.state.runId !== runId) {
    elements.state.history = [];
    elements.state.runId = runId;
  }
  elements.state.history.push(detail);
  if (elements.state.history.length > MAX_HISTORY) elements.state.history.shift();
  elements.state.index = elements.state.history.length - 1;
  elements.render();
});

app.registerExtension({
  name: "h3studio.taeh3-preview",
  async nodeCreated(node) {
    if (node.comfyClass === TARGET) installPreview(node);
  },
});
