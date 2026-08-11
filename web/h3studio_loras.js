import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { applyState, stateFromNode } from "./js/studio_extension.js";

const TARGET = "H3StudioDirector";
const MAX_CUSTOM_LORAS = 6;
const MIN_STRENGTH = -4;
const MAX_STRENGTH = 4;
const STRENGTH_STEP = 0.05;
const CATALOG_URL = "/h3studio/loras";
const STYLE_ID = "h3studio-custom-loras-style";

let catalog = [];
let catalogPromise = null;

function clamp(value, min, max, fallback = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.max(min, Math.min(max, number));
}

function normalizeStack(value) {
  if (!Array.isArray(value)) return [];
  return value.slice(0, MAX_CUSTOM_LORAS).map((item) => ({
    name: String(item?.name || "").replaceAll("\\", "/").trim(),
    strength: clamp(item?.strength, MIN_STRENGTH, MAX_STRENGTH, 1),
    enabled: item?.enabled !== false,
  }));
}

function formatSize(bytes) {
  const value = Number(bytes) || 0;
  if (value <= 0) return "";
  if (value >= 1024 ** 3) return `${(value / (1024 ** 3)).toFixed(2)} GiB`;
  if (value >= 1024 ** 2) return `${(value / (1024 ** 2)).toFixed(0)} MiB`;
  return `${Math.round(value / 1024)} KiB`;
}

async function loadCatalog(force = false) {
  if (!force && catalog.length) return catalog;
  if (!force && catalogPromise) return catalogPromise;
  catalogPromise = (async () => {
    const response = typeof api.fetchApi === "function"
      ? await api.fetchApi(CATALOG_URL)
      : await fetch(CATALOG_URL, { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error(`LoRA catalog request failed (${response.status})`);
    const payload = await response.json();
    if (payload?.error) throw new Error(payload.error);
    catalog = Array.isArray(payload?.items) ? payload.items : [];
    return catalog;
  })();
  try {
    return await catalogPromise;
  } finally {
    catalogPromise = null;
  }
}

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .h3s-lora-stack { display:flex; flex-direction:column; gap:8px; }
    .h3s-lora-toolbar { display:flex; align-items:center; justify-content:space-between; gap:8px; flex-wrap:wrap; }
    .h3s-lora-toolbar-actions { display:flex; gap:6px; }
    .h3s-lora-button { border:1px solid var(--h3s-border,#35414a); background:var(--h3s-panel-2,#172127); color:inherit; border-radius:7px; padding:6px 9px; cursor:pointer; font:inherit; }
    .h3s-lora-button:hover:not(:disabled) { border-color:var(--h3s-accent,#00cfa6); }
    .h3s-lora-button:disabled { opacity:.42; cursor:not-allowed; }
    .h3s-lora-row { display:grid; grid-template-columns:auto minmax(150px,1fr) 150px auto; gap:8px; align-items:center; padding:8px; border:1px solid var(--h3s-border,#35414a); border-radius:9px; background:color-mix(in srgb,var(--h3s-panel-2,#172127) 88%,transparent); }
    .h3s-lora-row.is-disabled { opacity:.58; }
    .h3s-lora-enable { display:flex; align-items:center; justify-content:center; }
    .h3s-lora-select { min-width:0; width:100%; }
    .h3s-lora-strength { display:grid; grid-template-columns:minmax(70px,1fr) 64px; gap:6px; align-items:center; }
    .h3s-lora-strength input[type=range] { width:100%; min-width:70px; accent-color:var(--h3s-accent,#00cfa6); }
    .h3s-lora-strength input[type=number] { width:64px; box-sizing:border-box; }
    .h3s-lora-actions { display:flex; gap:3px; }
    .h3s-lora-icon { min-width:28px; padding:5px 6px; }
    .h3s-lora-empty { padding:11px; border:1px dashed var(--h3s-border,#35414a); border-radius:9px; opacity:.75; }
    .h3s-lora-status { font-size:11px; opacity:.72; }
    .h3s-lora-warning { color:#f3b66b; font-size:11px; line-height:1.45; }
    @media (max-width:650px) { .h3s-lora-row { grid-template-columns:auto minmax(120px,1fr) auto; } .h3s-lora-strength { grid-column:2 / -1; } }
  `;
  document.head.append(style);
}

function stateStack(node) {
  const state = stateFromNode(node);
  return { state, stack: normalizeStack(state.ui?.custom_loras) };
}

function saveStack(node, state, stack) {
  state.ui = { ...state.ui, custom_loras: normalizeStack(stack) };
  applyState(node, state);
  node.setDirtyCanvas?.(true, true);
}

function button(text, title, click, className = "") {
  const value = document.createElement("button");
  value.type = "button";
  value.className = `h3s-lora-button ${className}`.trim();
  value.textContent = text;
  value.title = title;
  value.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    click();
  });
  return value;
}

function loraSelect(item, index, stack, onChange) {
  const select = document.createElement("select");
  select.className = "h3s-lora-select";
  select.setAttribute("aria-label", `Custom LoRA ${index + 1}`);
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = catalog.length ? "Choose installed LoRA…" : "No LoRAs found";
  select.append(placeholder);

  const seen = new Set();
  if (item.name && !catalog.some((entry) => entry.name === item.name)) {
    const missing = document.createElement("option");
    missing.value = item.name;
    missing.textContent = `${item.name} · missing`;
    select.append(missing);
    seen.add(item.name);
  }
  for (const entry of catalog) {
    if (!entry?.name || seen.has(entry.name)) continue;
    const option = document.createElement("option");
    option.value = entry.name;
    option.textContent = `${entry.name}${entry.size_bytes ? ` · ${formatSize(entry.size_bytes)}` : ""}`;
    select.append(option);
    seen.add(entry.name);
  }
  select.value = item.name;
  select.addEventListener("change", () => {
    const duplicate = stack.some((other, otherIndex) => otherIndex !== index && other.name && other.name === select.value);
    if (duplicate) {
      app.extensionManager?.toast?.add?.({
        severity: "warn",
        summary: "LoRA already in stack",
        detail: "Use one row and adjust its strength instead of loading the same LoRA twice.",
        life: 4500,
      });
      select.value = item.name;
      return;
    }
    onChange({ name: select.value });
  });
  return select;
}

function strengthControl(item, onChange) {
  const wrap = document.createElement("div");
  wrap.className = "h3s-lora-strength";
  const range = document.createElement("input");
  range.type = "range";
  range.min = String(MIN_STRENGTH);
  range.max = String(MAX_STRENGTH);
  range.step = String(STRENGTH_STEP);
  range.value = String(item.strength);
  range.title = "LoRA model strength";
  const number = document.createElement("input");
  number.type = "number";
  number.min = String(MIN_STRENGTH);
  number.max = String(MAX_STRENGTH);
  number.step = String(STRENGTH_STEP);
  number.value = String(item.strength);
  number.setAttribute("aria-label", "LoRA strength");
  const update = (raw) => {
    const value = Math.round(clamp(raw, MIN_STRENGTH, MAX_STRENGTH, 1) / STRENGTH_STEP) * STRENGTH_STEP;
    range.value = String(value);
    number.value = String(value);
    onChange({ strength: value });
  };
  range.addEventListener("input", () => {
    number.value = range.value;
  });
  range.addEventListener("change", () => update(range.value));
  number.addEventListener("change", () => update(number.value));
  wrap.append(range, number);
  return wrap;
}

function row(node, state, stack, item, index, rerender) {
  const root = document.createElement("div");
  root.className = `h3s-lora-row${item.enabled ? "" : " is-disabled"}`;
  const enabled = document.createElement("label");
  enabled.className = "h3s-lora-enable";
  enabled.title = "Enable this LoRA";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = item.enabled;
  checkbox.setAttribute("aria-label", `Enable custom LoRA ${index + 1}`);
  checkbox.addEventListener("change", () => {
    stack[index] = { ...stack[index], enabled: checkbox.checked };
    saveStack(node, state, stack);
    rerender();
  });
  enabled.append(checkbox);

  const patch = (value) => {
    stack[index] = { ...stack[index], ...value };
    saveStack(node, state, stack);
    rerender();
  };
  const select = loraSelect(item, index, stack, patch);
  const strength = strengthControl(item, patch);
  const actions = document.createElement("div");
  actions.className = "h3s-lora-actions";
  const up = button("↑", "Move LoRA earlier", () => {
    if (index <= 0) return;
    [stack[index - 1], stack[index]] = [stack[index], stack[index - 1]];
    saveStack(node, state, stack);
    rerender();
  }, "h3s-lora-icon");
  const down = button("↓", "Move LoRA later", () => {
    if (index >= stack.length - 1) return;
    [stack[index + 1], stack[index]] = [stack[index], stack[index + 1]];
    saveStack(node, state, stack);
    rerender();
  }, "h3s-lora-icon");
  const remove = button("×", "Remove LoRA", () => {
    stack.splice(index, 1);
    saveStack(node, state, stack);
    rerender();
  }, "h3s-lora-icon");
  up.disabled = index === 0;
  down.disabled = index === stack.length - 1;
  actions.append(up, down, remove);
  root.append(enabled, select, strength, actions);
  return root;
}

function buildSection(node) {
  const { state, stack } = stateStack(node);
  const section = document.createElement("section");
  section.className = "h3s-section h3s-custom-loras";
  section.dataset.h3studioCustomLoras = "true";
  const header = document.createElement("div");
  header.className = "h3s-section-header";
  const title = document.createElement("span");
  title.className = "h3s-section-title";
  title.textContent = "Custom LoRAs";
  const status = document.createElement("span");
  status.className = "h3s-status-pill";
  status.textContent = `${stack.filter((item) => item.enabled && item.name).length}/${MAX_CUSTOM_LORAS} active`;
  header.append(title, status);

  const body = document.createElement("div");
  body.className = "h3s-section-stack";
  const help = document.createElement("p");
  help.className = "h3s-context-help";
  help.textContent = "Stack style, character, detail or other model LoRAs after the selected Speed profile. Each row has its own model strength. H3 Studio uses ComfyUI bypass-forward when available, so quantized H3 weights are not merged and requantized.";
  const warning = document.createElement("p");
  warning.className = "h3s-lora-warning";
  warning.textContent = "Order matters. LightX/PDD acceleration is already applied by Speed; do not add the same acceleration LoRA here again. Custom LoRAs must actually be compatible with MiniMax H3.";

  const stackRoot = document.createElement("div");
  stackRoot.className = "h3s-lora-stack";
  const rerender = () => installLoraSection(node, true);
  if (!stack.length) {
    const empty = document.createElement("div");
    empty.className = "h3s-lora-empty";
    empty.textContent = "No custom LoRAs. Base/LightX/PDD behavior stays unchanged.";
    stackRoot.append(empty);
  } else {
    stack.forEach((item, index) => stackRoot.append(row(node, state, stack, item, index, rerender)));
  }

  const toolbar = document.createElement("div");
  toolbar.className = "h3s-lora-toolbar";
  const catalogStatus = document.createElement("span");
  catalogStatus.className = "h3s-lora-status";
  catalogStatus.textContent = node.__h3studioLoraCatalogError
    || (catalog.length ? `${catalog.length} installed LoRA${catalog.length === 1 ? "" : "s"}` : "Loading installed LoRAs…");
  const toolbarActions = document.createElement("div");
  toolbarActions.className = "h3s-lora-toolbar-actions";
  const refresh = button("Refresh", "Refresh ComfyUI/models/loras", async () => {
    refresh.disabled = true;
    catalogStatus.textContent = "Refreshing…";
    try {
      await loadCatalog(true);
      node.__h3studioLoraCatalogError = "";
      rerender();
    } catch (error) {
      node.__h3studioLoraCatalogError = String(error?.message || error);
      catalogStatus.textContent = node.__h3studioLoraCatalogError;
      refresh.disabled = false;
    }
  });
  const add = button("+ Add LoRA", "Add an installed custom LoRA", () => {
    if (stack.length >= MAX_CUSTOM_LORAS) return;
    const already = new Set(stack.map((item) => item.name));
    const firstUnused = catalog.find((entry) => entry?.name && !already.has(entry.name))?.name || "";
    stack.push({ name: firstUnused, strength: 1, enabled: true });
    saveStack(node, state, stack);
    rerender();
  });
  add.disabled = stack.length >= MAX_CUSTOM_LORAS;
  toolbarActions.append(refresh, add);
  toolbar.append(catalogStatus, toolbarActions);
  body.append(help, warning, stackRoot, toolbar);
  section.append(header, body);
  return section;
}

function installLoraSection(node, replace = false) {
  const panel = node?.__h3studioPanel;
  if (!panel?.isConnected) return;
  const existing = panel.querySelector(":scope > .h3s-custom-loras");
  if (existing && !replace) return;
  const section = buildSection(node);
  if (existing) {
    existing.replaceWith(section);
  } else {
    const advanced = [...panel.children].find((child) => child.querySelector?.(".h3s-advanced-toggle"));
    panel.insertBefore(section, advanced || null);
  }
}

function watchDirector(node) {
  if (node.__h3studioLoraObserver || node.__h3studioLoraWatchPending) return;
  node.__h3studioLoraWatchPending = true;
  let attempts = 0;
  const wait = () => {
    const panel = node.__h3studioPanel;
    if (!panel) {
      attempts += 1;
      if (attempts < 600) setTimeout(wait, 25);
      else node.__h3studioLoraWatchPending = false;
      return;
    }
    node.__h3studioLoraWatchPending = false;
    installStyles();
    installLoraSection(node);
    const observer = new MutationObserver(() => {
      if (!panel.querySelector(":scope > .h3s-custom-loras")) installLoraSection(node);
    });
    observer.observe(panel, { childList: true });
    node.__h3studioLoraObserver = observer;
    loadCatalog().then(() => {
      node.__h3studioLoraCatalogError = "";
      installLoraSection(node, true);
    }).catch((error) => {
      node.__h3studioLoraCatalogError = String(error?.message || error);
      installLoraSection(node, true);
    });
  };
  setTimeout(wait, 0);
}

app.registerExtension({
  name: "H3Studio.CustomLoRAs",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== TARGET) return;
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function h3studioCustomLorasCreated() {
      const result = originalCreated?.apply(this, arguments);
      watchDirector(this);
      return result;
    };
  },
});

export { MAX_CUSTOM_LORAS, normalizeStack };
