import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const TARGET = "H3StudioTAEH3Preview";
const MAX_HISTORY = 40;

function openLightbox(source, label) {
  if (!source) return;
  const overlay = document.createElement("div");
  overlay.className = "h3s-preview-lightbox";
  overlay.tabIndex = -1;
  const image = document.createElement("img");
  image.src = source;
  image.alt = label || "Expanded TAEH3 sampling preview";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "h3s-preview-lightbox-close";
  close.textContent = "×";
  close.title = "Close preview";
  const dismiss = () => overlay.remove();
  close.addEventListener("click", dismiss);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) dismiss();
  });
  overlay.addEventListener("keydown", (event) => {
    if (event.key === "Escape") dismiss();
  });
  overlay.append(image, close);
  document.body.append(overlay);
  overlay.focus();
}

function installPreview(node) {
  if (node.__h3studioPreviewInstalled || typeof node.addDOMWidget !== "function") return;
  node.__h3studioPreviewInstalled = true;
  const root = document.createElement("div");
  root.className = "h3s-live-preview";
  const image = document.createElement("img");
  image.alt = "TAEH3 live sampling preview";
  image.title = "Click to expand";
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
  root.append(image, empty, navigation, status);

  const state = { history: [], index: -1, runId: null };
  const render = () => {
    const frame = state.history[state.index];
    if (!frame) return;
    image.src = frame.image;
    image.hidden = false;
    empty.hidden = true;
    status.textContent = `Step ${frame.step}/${frame.total} · ${frame.width} × ${frame.height}`;
    position.textContent = `${state.index + 1} / ${state.history.length}`;
    previous.disabled = state.index <= 0;
    next.disabled = state.index >= state.history.length - 1;
    navigation.hidden = state.history.length < 2;
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
  image.addEventListener("click", (event) => {
    event.stopPropagation();
    const frame = state.history[state.index];
    openLightbox(frame?.image, status.textContent);
  });
  navigation.hidden = true;
  node.__h3studioPreviewElements = { state, render };
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
  const runId = String(detail.run_id || "");
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
