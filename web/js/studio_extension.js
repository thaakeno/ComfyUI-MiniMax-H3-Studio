import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

import {
  ASPECT_RATIOS,
  FRAME_PROFILES,
  MAX_REFERENCES,
  RETENTION,
  ROLES,
  SAMPLING_PROFILES,
  normalizeState,
  parseState,
  planResolution,
  serializeState,
} from "./core/state.js";
import { element, field, iconButton, numberControl, rangeControl, selectControl } from "./core/dom.js";
import { installTheme } from "./core/theme.js";
import { chooseImageFiles, previewUrlForStorage, uploadImage } from "./features/image_upload.js";

const TARGET = "H3StudioDirector";
const LINKS_PROPERTY = "h3studio_virtual_media_links";
const PANEL_HEIGHT = 500;
const HIDDEN_WIDGETS = new Set([
  "mode", "resolution", "aspect_ratio", "width", "height", "seconds", "advanced", "fps",
  "keyframe_role", "ref_image_size", "reference_mention_mode", "megapixels", "seed", "enhance_mode",
  "adherence", "route", "sampling_profile", "frame_profile", "analyzer_model", "studio_state",
]);

for (let index = 1; index <= MAX_REFERENCES; index += 1) {
  HIDDEN_WIDGETS.add(`media_filename_${index}`);
  HIDDEN_WIDGETS.add(`media_type_${index}`);
  HIDDEN_WIDGETS.add(`role_${index}`);
  HIDDEN_WIDGETS.add(`retention_${index}`);
  HIDDEN_WIDGETS.add(`description_${index}`);
}

function widget(node, name) {
  return node.widgets?.find((candidate) => candidate.name === name) || null;
}

function setWidget(node, name, value, invoke = false) {
  const target = widget(node, name);
  if (!target || target.value === value) return;
  target.value = value;
  if (invoke) target.callback?.(value, app.canvas, node, [0, 0], {});
}

function hideWidget(target) {
  if (!target || target.__h3studioHidden) return;
  target.__h3studioHidden = true;
  target.__h3studioComputeSize = target.computeSize;
  target.computeSize = () => [0, -4];
  target.hidden = true;
}

function sourceNode(link) {
  if (!link) return null;
  return app.graph?.getNodeById?.(Number(link.source_id)) || null;
}

function plainFilename(value) {
  const candidate = typeof value === "object" ? value?.filename || value?.name : value;
  const text = String(candidate || "").trim();
  if (!text || /^(data:|blob:|https?:)/i.test(text)) return "";
  return text.split(/[\\/]/).pop() || "";
}

function sourceFilename(source, ordinal) {
  const preferred = ["image", "filename", "file", "upload"];
  const widgets = source?.widgets || [];
  for (const name of preferred) {
    const value = widgets.find((candidate) => String(candidate.name).toLowerCase() === name)?.value;
    const filename = plainFilename(value);
    if (filename) return filename;
  }
  for (const candidate of widgets) {
    const filename = plainFilename(candidate.value);
    if (/\.(png|jpe?g|webp|gif|bmp|tiff?)$/i.test(filename)) return filename;
  }
  return plainFilename(source?.properties?.filename) || `image_${ordinal}.png`;
}

function sourcePreview(source) {
  const direct = source?.imgs?.[0]?.src || source?.image?.src;
  if (direct) return direct;
  const widgetValue = source?.widgets?.find((candidate) => String(candidate.name).toLowerCase() === "image")?.value;
  const filename = typeof widgetValue === "object" ? widgetValue?.filename || widgetValue?.name : widgetValue;
  if (!filename || typeof filename !== "string") return "";
  const type = typeof widgetValue === "object" ? widgetValue.type || "input" : "input";
  const subfolder = typeof widgetValue === "object" ? widgetValue.subfolder || "" : "";
  const query = new URLSearchParams({ filename, type, subfolder, preview: "webp;90" });
  return `/view?${query.toString()}`;
}

function normalizedLinks(node) {
  const raw = Array.isArray(node.properties?.[LINKS_PROPERTY]) ? node.properties[LINKS_PROPERTY] : [];
  const seen = new Set();
  return raw
    .filter((link) => String(link?.media_type || "image") === "image")
    .filter((link) => {
      const key = `${Number(link?.source_id)}:${Number(link?.source_slot) || 0}`;
      if (!Number.isFinite(Number(link?.source_id)) || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, MAX_REFERENCES)
    .map((link, index) => ({
      source_id: Number(link.source_id),
      source_slot: Number(link.source_slot) || 0,
      media_type: "image",
      order: index + 1,
    }));
}

function writeLinks(node, links) {
  node.properties ||= {};
  node.properties[LINKS_PROPERTY] = links.map((link, index) => ({ ...link, media_type: "image", order: index + 1 }));
}

function linkSignature(node) {
  return normalizedLinks(node).map((link) => `${link.source_id}:${link.source_slot}`).join("|");
}

function referenceForLink(previous, link, ordinal) {
  const bySource = previous.references.find(
    (reference) => String(reference.source_node_id) === String(link.source_id) && reference.source_slot === link.source_slot,
  );
  const byOrdinal = previous.references[ordinal - 1];
  const inherited = bySource || byOrdinal || {};
  return {
    id: inherited.id || `node_${link.source_id}_${link.source_slot}`,
    filename: sourceFilename(sourceNode(link), ordinal),
    storage_name: "",
    ordinal,
    role: inherited.role || "auto",
    retention: inherited.retention || "attribute_transfer",
    description: inherited.description || "",
    enabled: true,
    source_node_id: String(link.source_id),
    source_slot: link.source_slot,
  };
}

function linkKey(link) {
  return `${Number(link.source_id)}:${Number(link.source_slot) || 0}`;
}

function writeLinksFromReferences(node, references) {
  const byKey = new Map(normalizedLinks(node).map((link) => [linkKey(link), link]));
  writeLinks(node, references
    .filter((reference) => reference.source_node_id != null)
    .map((reference) => byKey.get(`${Number(reference.source_node_id)}:${Number(reference.source_slot) || 0}`))
    .filter(Boolean));
}

function notifyReferenceChange(node) {
  globalThis.dispatchEvent?.(new CustomEvent("h3studio:references-changed", { detail: { nodeId: Number(node.id) } }));
}

function stateFromNode(node) {
  const persisted = parseState(widget(node, "studio_state")?.value);
  const links = normalizedLinks(node);
  const available = new Map(links.map((link) => [linkKey(link), link]));
  const used = new Set();
  const references = [];
  for (const reference of persisted.references) {
    if (reference.source_node_id == null) {
      if (reference.storage_name) references.push(reference);
      continue;
    }
    const key = `${Number(reference.source_node_id)}:${Number(reference.source_slot) || 0}`;
    const link = available.get(key);
    if (!link) continue;
    used.add(key);
    references.push(referenceForLink(persisted, link, references.length + 1));
  }
  for (const link of links) {
    if (used.has(linkKey(link))) continue;
    references.push(referenceForLink(persisted, link, references.length + 1));
  }
  persisted.prompt = String(widget(node, "prompt")?.value || persisted.prompt || "");
  persisted.references = references.map((reference, index) => ({ ...reference, ordinal: index + 1 }));
  return normalizeState(persisted);
}

function applyState(node, state, dirty = true) {
  const normalized = normalizeState(state);
  const generation = normalized.generation;
  const options = normalized.prompt_options;
  const resolution = planResolution(
    generation.aspect_ratio,
    generation.megapixels,
    generation.custom_width,
    generation.custom_height,
    generation.cap_native_resolution,
  );
  setWidget(node, "mode", normalized.references.length || generation.mode === "reference_edit" ? "reference" : "image");
  setWidget(node, "resolution", "Custom");
  setWidget(node, "aspect_ratio", generation.aspect_ratio);
  setWidget(node, "width", resolution.width);
  setWidget(node, "height", resolution.height);
  setWidget(node, "megapixels", generation.megapixels);
  setWidget(node, "seed", generation.seed);
  setWidget(node, "enhance_mode", options.enhance_mode);
  setWidget(node, "adherence", options.adherence);
  setWidget(node, "route", generation.route);
  setWidget(node, "sampling_profile", generation.sampling_profile);
  setWidget(node, "frame_profile", generation.frame_profile);
  setWidget(node, "analyzer_model", options.analyzer_model);
  setWidget(node, "studio_state", serializeState(normalized));
  for (let index = 1; index <= MAX_REFERENCES; index += 1) {
    const reference = normalized.references[index - 1];
    setWidget(node, `media_filename_${index}`, reference?.storage_name || reference?.filename || "");
    setWidget(node, `media_type_${index}`, "image");
    setWidget(node, `role_${index}`, reference?.role || "auto");
    setWidget(node, `retention_${index}`, reference?.retention || "attribute_transfer");
    setWidget(node, `description_${index}`, reference?.description || "");
  }
  node.__h3studioState = normalized;
  if (dirty) {
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
  }
  return normalized;
}

function controlRow(label, control) {
  return field(label, control);
}

function section(title, body, accessory = null) {
  const header = element("div", { className: "h3s-section-header" }, [
    element("span", { className: "h3s-section-title", text: title }),
    accessory,
  ]);
  return element("section", { className: "h3s-section" }, [header, body]);
}

function generationSection(node, state, refresh) {
  const generation = state.generation;
  const update = (patch) => {
    state.generation = { ...state.generation, ...patch };
    applyState(node, state);
    refresh();
  };
  const mode = selectControl(generation.mode, [
    ["auto", "Auto"], ["text_to_image", "Text to image"], ["image_to_image", "Image to image"],
    ["reference_edit", "Reference edit"],
  ], "Generation mode", (value) => update({ mode: value }));
  const ratio = selectControl(generation.aspect_ratio, Object.keys(ASPECT_RATIOS), "Aspect ratio", (value) => update({ aspect_ratio: value }));
  const megapixels = numberControl(generation.megapixels, { min: 0.2, max: 2, step: 0.05 }, "Megapixels", (value) => update({ megapixels: value }));
  const seed = numberControl(generation.seed, { min: 0, max: Number.MAX_SAFE_INTEGER, step: 1 }, "Seed", (value) => update({ seed: Math.max(0, Math.trunc(value)) }));
  const random = iconButton("Randomize seed", "↻", () => update({ seed: Math.floor(Math.random() * 0x7fffffff) }));
  const seedWrap = element("div", { className: "h3s-seed-row" }, [seed, random]);
  const plan = planResolution(generation.aspect_ratio, generation.megapixels, generation.custom_width, generation.custom_height, true);
  const preview = element("div", { className: "h3s-resolution-preview" }, [
    element("span", { text: `${plan.width} × ${plan.height}` }),
    element("span", { text: `${plan.actualMegapixels.toFixed(2)} MP${plan.capped ? " · native cap" : ""}` }),
  ]);
  const grid = element("div", { className: "h3s-grid" }, [
    controlRow("Mode", mode), controlRow("Aspect", ratio), controlRow("Megapixels", megapixels), controlRow("Seed", seedWrap),
  ]);
  return section("Generation", element("div", {}, [grid, preview]));
}

function promptSection(node, state, refresh) {
  const update = (patch) => {
    state.prompt_options = { ...state.prompt_options, ...patch };
    applyState(node, state);
    refresh();
  };
  const options = state.prompt_options;
  const enhance = selectControl(options.enhance_mode, [
    ["off", "Pass through"], ["compile_only", "Production brief"], ["vlm", "VLM analysis + brief"],
  ], "Prompt enhancement", (value) => update({ enhance_mode: value }));
  const adherenceValue = element("span", { className: "h3s-inline-value", text: `${Math.round(options.adherence * 100)}%` });
  const adherence = rangeControl(options.adherence, { min: 0, max: 1, step: 0.05 }, "Reference adherence", (value) => {
    adherenceValue.textContent = `${Math.round(value * 100)}%`;
    state.prompt_options.adherence = value;
    applyState(node, state);
  });
  const adherenceWrap = element("div", {}, [adherence, adherenceValue]);
  return section("Direction", element("div", { className: "h3s-grid" }, [
    controlRow("Enhancement", enhance), controlRow("Adherence", adherenceWrap),
  ]));
}

function referenceCard(node, state, reference, index, refresh) {
  const link = reference.source_node_id == null ? null : normalizedLinks(node).find(
    (candidate) => Number(candidate.source_id) === Number(reference.source_node_id)
      && Number(candidate.source_slot) === Number(reference.source_slot || 0),
  );
  const source = sourceNode(link);
  const preview = reference.storage_name ? previewUrlForStorage(reference.storage_name) : sourcePreview(source);
  const thumb = element("div", { className: "h3s-reference-thumb" }, [
    preview ? element("img", { src: preview, alt: "" }) : element("span", { className: "h3s-thumb-placeholder", text: "IMG" }),
    element("span", { className: "h3s-reference-index", text: `@${index + 1}` }),
  ]);
  const mutate = (patch) => {
    state.references[index] = { ...state.references[index], ...patch };
    applyState(node, state);
  };
  const move = (delta) => {
    const next = index + delta;
    if (next < 0 || next >= state.references.length) return;
    const reordered = [...state.references];
    [reordered[index], reordered[next]] = [reordered[next], reordered[index]];
    state.references = reordered.map((referenceItem, ordinal) => ({ ...referenceItem, ordinal: ordinal + 1 }));
    writeLinksFromReferences(node, state.references);
    applyState(node, state);
    notifyReferenceChange(node);
    refresh();
  };
  const remove = () => {
    if (reference.source_node_id != null) {
      writeLinks(node, normalizedLinks(node).filter((candidate) => linkKey(candidate) !== linkKey(link)));
    }
    state.references.splice(index, 1);
    state.references = state.references.map((referenceItem, ordinal) => ({ ...referenceItem, ordinal: ordinal + 1 }));
    applyState(node, state);
    notifyReferenceChange(node);
    refresh();
  };
  const actions = element("div", { className: "h3s-reference-actions" }, [
    iconButton("Move image up", "↑", () => move(-1)),
    iconButton("Move image down", "↓", () => move(1)),
    iconButton("Remove image", "×", remove, "h3s-danger"),
  ]);
  actions.children[0].disabled = index === 0;
  actions.children[1].disabled = index === state.references.length - 1;
  const title = element("div", { className: "h3s-reference-top" }, [
    element("span", { className: "h3s-reference-name", text: reference.filename, title: reference.filename }), actions,
  ]);
  const role = selectControl(reference.role, ROLES, `Role for Image ${index + 1}`, (value) => mutate({ role: value }));
  const retention = selectControl(reference.retention, RETENTION, `Retention for Image ${index + 1}`, (value) => mutate({ retention: value }));
  const description = element("textarea", {
    className: "h3s-reference-description", value: reference.description,
    placeholder: "What this image defines…", attrs: { "aria-label": `Description for Image ${index + 1}` },
    on: { change: (event) => mutate({ description: event.target.value }) },
  });
  const controls = element("div", { className: "h3s-reference-controls" }, [role, retention]);
  return element("article", { className: "h3s-reference-card" }, [thumb, element("div", { className: "h3s-reference-body" }, [title, controls, description])]);
}

async function addImages(node, state, refresh) {
  const capacity = MAX_REFERENCES - state.references.length;
  if (capacity <= 0 || node.__h3studioUploading) return;
  const files = (await chooseImageFiles({ multiple: true })).slice(0, capacity);
  if (!files.length) return;
  node.__h3studioUploading = true;
  node.__h3studioUploadError = "";
  node.__h3studioUploadLabel = `Uploading 0/${files.length}`;
  refresh();
  try {
    for (let index = 0; index < files.length; index += 1) {
      node.__h3studioUploadLabel = `Uploading ${index + 1}/${files.length}`;
      refresh();
      const uploaded = await uploadImage(api, files[index]);
      state.references.push({
        id: `upload_${globalThis.crypto?.randomUUID?.() || `${Date.now()}_${index}`}`,
        filename: uploaded.filename,
        storage_name: uploaded.storage_name,
        ordinal: state.references.length + 1,
        role: "auto",
        retention: "attribute_transfer",
        description: "",
        enabled: true,
        source_node_id: null,
        source_slot: 0,
      });
      applyState(node, state);
    }
    notifyReferenceChange(node);
  } catch (error) {
    node.__h3studioUploadError = error instanceof Error ? error.message : String(error);
  } finally {
    node.__h3studioUploading = false;
    node.__h3studioUploadLabel = "";
    refresh();
  }
}

function referencesSection(node, state, refresh) {
  const list = element("div", { className: "h3s-reference-list" });
  if (!state.references.length) {
    list.append(element("div", { className: "h3s-empty" }, [
      element("strong", { text: "Text-to-image ready" }),
      element("span", { text: "Upload images here to create @Image 1 through @Image 9. External image links remain supported." }),
    ]));
  } else {
    state.references.forEach((reference, index) => list.append(referenceCard(node, state, reference, index, refresh)));
  }
  if (node.__h3studioUploadError) {
    list.prepend(element("div", { className: "h3s-upload-error", text: node.__h3studioUploadError, attrs: { role: "alert" } }));
  }
  const addButton = element("button", {
    className: "h3s-add-image", type: "button",
    disabled: state.references.length >= MAX_REFERENCES || Boolean(node.__h3studioUploading),
    text: node.__h3studioUploading ? node.__h3studioUploadLabel || "Uploading…" : "+ Add images",
    attrs: { "aria-label": "Upload reference images" },
    on: { click: () => addImages(node, state, refresh) },
  });
  const accessory = element("div", { className: "h3s-reference-heading-actions" }, [
    element("span", { className: "h3s-status-pill", text: `${state.references.length}/${MAX_REFERENCES}` }),
    addButton,
  ]);
  return section("References", list, accessory);
}

function advancedSection(node, state, refresh) {
  const content = element("div", { className: "h3s-advanced-content h3s-grid" });
  content.hidden = !state.ui.advanced_open;
  const update = (generationPatch = {}, promptPatch = {}) => {
    state.generation = { ...state.generation, ...generationPatch };
    state.prompt_options = { ...state.prompt_options, ...promptPatch };
    applyState(node, state);
    refresh();
  };
  content.append(
    controlRow("Route", selectControl(state.generation.route, ["auto", "fl2va", "ref2va"], "Conditioning route", (value) => update({ route: value }))),
    controlRow("Sampling", selectControl(state.generation.sampling_profile, SAMPLING_PROFILES, "Sampling profile", (value) => update({ sampling_profile: value }))),
    controlRow("Frames", selectControl(state.generation.frame_profile, FRAME_PROFILES, "Frame profile", (value) => update({ frame_profile: value }))),
  );
  const model = element("input", {
    className: "h3s-control", type: "text", value: state.prompt_options.analyzer_model,
    placeholder: "Local Qwen-VL path (optional)", attrs: { "aria-label": "VLM analyzer model" },
    on: { change: (event) => update({}, { analyzer_model: event.target.value }) },
  });
  content.append(controlRow("Analyzer", model));
  const toggle = element("button", {
    className: "h3s-advanced-toggle", type: "button", attrs: { "aria-expanded": String(state.ui.advanced_open) },
    on: { click: () => { state.ui.advanced_open = !state.ui.advanced_open; applyState(node, state); refresh(); } },
  }, [element("span", { text: "Advanced controls" }), element("span", { text: state.ui.advanced_open ? "−" : "+" })]);
  return element("section", { className: "h3s-section" }, [toggle, content]);
}

function renderPanel(node) {
  const root = node.__h3studioPanel;
  if (!root) return;
  const state = applyState(node, stateFromNode(node), false);
  root.replaceChildren();
  const refresh = () => renderPanel(node);
  const resolvedMode = state.references.length ? "Reference ready" : "T2I ready";
  root.append(
    element("header", { className: "h3s-studio-header" }, [
      element("div", { className: "h3s-studio-brand" }, [element("span", { className: "h3s-studio-mark" }), element("span", { className: "h3s-studio-title", text: "MiniMax H3 Studio" })]),
      element("span", { className: "h3s-status-pill", text: resolvedMode }),
    ]),
    generationSection(node, state, refresh),
    promptSection(node, state, refresh),
    referencesSection(node, state, refresh),
    advancedSection(node, state, refresh),
  );
  node.__h3studioLinkSignature = linkSignature(node);
}

function installPanel(node) {
  if (node.__h3studioPanelInstalled || typeof node.addDOMWidget !== "function") return;
  node.__h3studioPanelInstalled = true;
  installTheme();
  for (const target of node.widgets || []) if (HIDDEN_WIDGETS.has(target.name)) hideWidget(target);
  const root = element("div", { className: "h3s-studio-panel", attrs: { role: "group", "aria-label": "MiniMax H3 Studio controls" } });
  node.__h3studioPanel = root;
  const panelWidget = node.addDOMWidget("h3studio_controls", "h3studio_controls", root, {
    serialize: false,
    hideOnZoom: false,
    getValue: () => undefined,
  });
  panelWidget.computeSize = (width) => [width, PANEL_HEIGHT];

  const originalSerialize = node.onSerialize;
  node.onSerialize = function h3studioSerialize(data) {
    applyState(this, stateFromNode(this), false);
    return originalSerialize?.apply(this, arguments);
  };
  const originalConfigure = node.onConfigure;
  node.onConfigure = function h3studioConfigure(data) {
    const result = originalConfigure?.apply(this, arguments);
    queueMicrotask(() => renderPanel(this));
    return result;
  };
  const originalConnectionsChange = node.onConnectionsChange;
  node.onConnectionsChange = function h3studioConnectionsChange() {
    const result = originalConnectionsChange?.apply(this, arguments);
    queueMicrotask(() => renderPanel(this));
    return result;
  };
  const originalForeground = node.onDrawForeground;
  node.onDrawForeground = function h3studioForeground(context) {
    originalForeground?.apply(this, arguments);
    const signature = linkSignature(this);
    if (signature !== this.__h3studioLinkSignature && !this.__h3studioRenderQueued) {
      this.__h3studioRenderQueued = true;
      queueMicrotask(() => {
        this.__h3studioRenderQueued = false;
        renderPanel(this);
      });
    }
  };
  node.size = [Math.max(430, node.size?.[0] || 0), Math.max(820, node.size?.[1] || 0)];
  renderPanel(node);
}

app.registerExtension({
  name: "H3Studio.Controls",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== TARGET) return;
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function h3studioCreated() {
      const result = originalCreated?.apply(this, arguments);
      queueMicrotask(() => installPanel(this));
      return result;
    };
  },
});

export { applyState, linkSignature, normalizedLinks, stateFromNode };
