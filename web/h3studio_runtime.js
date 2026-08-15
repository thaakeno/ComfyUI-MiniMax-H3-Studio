import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { applyState, stateFromNode } from "./js/studio_extension.js";
import { selectControl } from "./js/core/dom.js";

const TARGET = "H3StudioDirector";
const CAPABILITIES_URL = "/h3studio/runtime/capabilities";
const STYLE_ID = "h3studio-runtime-v4-style";

const PRESETS = [
  ["auto", "Auto", "Best default", "Chooses the fastest safe path from the real H3 workload."],
  ["fast", "Fast", "Max speed", "Prefer accelerated kernels and no chunking when memory allows."],
  ["quality", "Quality", "Conservative", "Prefer the conservative PyTorch attention path."],
  ["low_vram", "Low VRAM", "Memory saver", "Reduce transient attention peaks with exact head chunking."],
  ["og_current", "OG", "No override", "Leave H3's inherited runtime behavior unchanged."],
  ["extreme_low_vram", "Extreme", "Last resort", "Strongest memory-saving path for constrained GPUs."],
];
const ATTENTION = [
  ["auto", "Auto / preset"],
  ["og", "Inherited / OG"],
  ["comfy_kitchen", "Comfy Kitchen"],
  ["sage_mem_eff", "Sage · memory-efficient"],
  ["pytorch", "PyTorch"],
];
const HEAD_CHUNKS = [[0, "Auto / preset"], [1, "Off"], [2, "2 groups"], [4, "4 groups"], [8, "8 groups"], [16, "16 groups"]];

let capabilities = null;
let capabilitiesPromise = null;

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .h3s-runtime-section{overflow:visible!important}
    .h3rt{display:flex;flex-direction:column;gap:10px}
    .h3rt-copy{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
    .h3rt-copy p{margin:0;color:var(--h3s-muted);font-size:10px;line-height:1.45;max-width:610px}
    .h3rt-detect{flex:none;border:1px solid var(--h3s-border);border-radius:8px;background:var(--h3s-bg);color:var(--h3s-text);padding:6px 9px;cursor:pointer;font:650 9px/1.2 inherit}
    .h3rt-detect:hover{border-color:color-mix(in srgb,var(--h3s-accent) 55%,var(--h3s-border))}
    .h3rt-presets{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
    .h3rt-preset{position:relative;min-width:0;min-height:58px;padding:8px 9px;text-align:left;border:1px solid var(--h3s-border);border-radius:10px;background:color-mix(in srgb,var(--h3s-bg) 88%,white 2%);color:var(--h3s-text);cursor:pointer;transition:120ms ease}
    .h3rt-preset:hover{transform:translateY(-1px);border-color:color-mix(in srgb,var(--h3s-accent) 50%,var(--h3s-border));background:color-mix(in srgb,var(--h3s-accent) 5%,var(--h3s-bg))}
    .h3rt-preset.is-active{border-color:color-mix(in srgb,var(--h3s-accent) 72%,var(--h3s-border));background:linear-gradient(145deg,color-mix(in srgb,var(--h3s-accent) 14%,var(--h3s-bg)),color-mix(in srgb,var(--h3s-accent) 5%,var(--h3s-bg)));box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--h3s-accent) 13%,transparent)}
    .h3rt-preset-name{display:block;font-size:11px;font-weight:760;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.h3rt-preset-sub{display:block;margin-top:2px;color:var(--h3s-muted);font-size:8.5px}.h3rt-preset.is-active .h3rt-preset-sub{color:color-mix(in srgb,var(--h3s-accent) 72%,var(--h3s-text))}
    .h3rt-more{display:grid;grid-template-columns:1fr 1fr;gap:6px;grid-column:1/-1}
    .h3rt-status{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
    .h3rt-chip{min-width:0;padding:7px 8px;border:1px solid color-mix(in srgb,var(--h3s-border) 88%,transparent);border-radius:9px;background:color-mix(in srgb,var(--h3s-bg) 93%,white 2%)}
    .h3rt-chip b{display:block;color:var(--h3s-muted);font-size:8px;font-weight:650;text-transform:uppercase;letter-spacing:.07em}.h3rt-chip span{display:block;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:10px}
    .h3rt-result{padding:9px 10px;border:1px solid color-mix(in srgb,var(--h3s-accent) 38%,var(--h3s-border));border-radius:10px;background:color-mix(in srgb,var(--h3s-accent) 6%,var(--h3s-bg))}
    .h3rt-result-head{display:flex;justify-content:space-between;gap:8px;align-items:center}.h3rt-result-head strong{font-size:11px}.h3rt-result-tag{font-size:8px;color:var(--h3s-accent);text-transform:uppercase;letter-spacing:.08em}
    .h3rt-result-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px 10px;margin-top:7px}.h3rt-kv{min-width:0}.h3rt-kv small{display:block;color:var(--h3s-muted);font-size:8px}.h3rt-kv span{display:block;font-size:9.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .h3rt-reason{margin-top:7px;color:var(--h3s-muted);font-size:9px;line-height:1.4}.h3rt-warning{margin-top:5px;color:#f4bf77;font-size:9px;line-height:1.4}
    .h3rt-expert{border-top:1px solid color-mix(in srgb,var(--h3s-border) 70%,transparent);padding-top:7px}.h3rt-expert>summary{cursor:pointer;color:var(--h3s-muted);font-size:9px;user-select:none;list-style:none}.h3rt-expert>summary::-webkit-details-marker{display:none}.h3rt-expert>summary::before{content:'›';display:inline-block;margin-right:6px;transition:transform .12s}.h3rt-expert[open]>summary::before{transform:rotate(90deg)}
    .h3rt-expert-grid{display:grid;grid-template-columns:1fr 1fr auto;gap:7px;align-items:end;margin-top:8px}.h3rt-field>span{display:block;margin:0 0 3px 1px;color:var(--h3s-muted);font-size:8.5px}.h3rt-reset{height:31px;border:1px solid var(--h3s-border);border-radius:8px;background:transparent;color:var(--h3s-muted);padding:0 9px;cursor:pointer;font-size:9px}.h3rt-reset:hover{color:var(--h3s-text)}
    .h3rt-expert-note{grid-column:1/-1;color:var(--h3s-muted);font-size:8.5px;line-height:1.4}.h3rt-expert-note strong{color:#f4bf77;font-weight:650}
    @media(max-width:720px){.h3rt-presets{grid-template-columns:1fr 1fr}.h3rt-status,.h3rt-result-grid{grid-template-columns:1fr 1fr}.h3rt-expert-grid{grid-template-columns:1fr}}
  `;
  document.head.append(style);
}

async function loadCapabilities(force = false) {
  if (!force && capabilities) return capabilities;
  if (!force && capabilitiesPromise) return capabilitiesPromise;
  capabilitiesPromise = (async () => {
    const response = await api.fetchApi(CAPABILITIES_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`Runtime capability request failed (${response.status})`);
    capabilities = (await response.json())?.capabilities || null;
    return capabilities;
  })();
  try { return await capabilitiesPromise; } finally { capabilitiesPromise = null; }
}

function runtimeState(node) {
  const state = stateFromNode(node);
  const ui = { ...(state.ui || {}) };
  return {
    state,
    preset: String(ui.runtime_optimization || "auto"),
    advanced: {
      attention_backend: "auto",
      head_chunks: 0,
      ffn_chunks: 0,
      ffn_sequence_threshold: 4096,
      ...(ui.runtime_advanced || {}),
    },
  };
}

function saveRuntime(node, state, preset, advanced, dirty = true) {
  state.ui = {
    ...(state.ui || {}),
    director_node_id: String(node.id),
    runtime_optimization: preset,
    runtime_advanced: advanced,
  };
  applyState(node, state, dirty);
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function chip(label, value, title = "") {
  const root = el("div", "h3rt-chip");
  const key = el("b", "", label);
  const val = el("span", "", value);
  val.title = title || value;
  root.append(key, val);
  return root;
}

function bool(value) { return value ? "ready" : "not available"; }
function vram(value) { return Number(value) > 0 ? `${Number(value).toFixed(1)} GB` : "unknown"; }

function presetButton(node, key, name, sub, description, active, compact = false) {
  const button = el("button", "h3rt-preset" + (active ? " is-active" : ""));
  button.type = "button";
  button.title = description;
  button.dataset.runtimePreset = key;
  button.append(el("span", "h3rt-preset-name", name), el("span", "h3rt-preset-sub", sub));
  if (compact) button.style.minHeight = "42px";
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    const current = runtimeState(node);
    if (current.preset === key) return;
    saveRuntime(node, current.state, key, current.advanced);
    installRuntimeSection(node, true);
  });
  return button;
}

function actualResult(node, requested) {
  const data = node.__h3studioRuntimeResolved;
  const root = el("div", "h3rt-result");
  const head = el("div", "h3rt-result-head");
  const title = el("strong", "", data ? `${data.requested_label} → ${data.resolved_label}` : (PRESETS.find(([key]) => key === requested)?.[1] || requested));
  head.append(title, el("span", "h3rt-result-tag", data ? "resolved last run" : "resolves on next run"));
  root.append(head);
  if (!data) {
    root.append(el("div", "h3rt-reason", requested === "auto"
      ? "Auto waits for real packed tokens, route, references and frame count before choosing the backend."
      : "The exact backend and chunking will appear here after the next generation."));
    return root;
  }
  const work = data.workload || {};
  const grid = el("div", "h3rt-result-grid");
  const pairs = [
    ["Attention", data.attention_label || data.attention_backend || "inherited"],
    ["Head chunks", Number(data.head_chunks) > 1 ? String(data.head_chunks) : "off"],
    ["Packed tokens", Number(work.sequence_length || 0).toLocaleString()],
    ["Workload", `${String(work.route || "").toUpperCase()} · ${work.frames || "?"}f · ${Number(work.megapixels || 0).toFixed(2)} MP`],
    ["VAE", data.vae_mode || "native H3"],
    ["Sampling", `${data.sampling_profile || ""} · unchanged`],
  ];
  for (const [key, value] of pairs) {
    const item = el("div", "h3rt-kv");
    item.append(el("small", "", key), el("span", "", String(value)));
    grid.append(item);
  }
  root.append(grid, el("div", "h3rt-reason", `Why: ${data.reason || "No reason reported."}`));
  for (const warning of [...(data.warnings || []), ...(data.fallbacks || []), ...(data.patch_notes || [])]) {
    if (!warning || String(warning).includes("runtime_patch_cache=hit")) continue;
    root.append(el("div", "h3rt-warning", String(warning)));
  }
  return root;
}

function expert(node, state, preset, advanced) {
  const root = el("details", "h3rt-expert");
  const summary = el("summary", "", "Expert overrides");
  const grid = el("div", "h3rt-expert-grid");
  const patch = (next) => {
    const current = runtimeState(node);
    saveRuntime(node, current.state, current.preset, { ...current.advanced, ...next });
    installRuntimeSection(node, true);
  };
  const attention = selectControl(advanced.attention_backend, ATTENTION, "Attention backend", (value) => patch({ attention_backend: value }));
  const heads = selectControl(advanced.head_chunks, HEAD_CHUNKS, "Attention head chunks", (value) => patch({ head_chunks: Number(value) }));
  const attentionField = el("div", "h3rt-field"); attentionField.append(el("span", "", "Attention backend"), attention);
  const headField = el("div", "h3rt-field"); headField.append(el("span", "", "Head chunking"), heads);
  const reset = el("button", "h3rt-reset", "Reset overrides"); reset.type = "button";
  reset.addEventListener("click", () => patch({ attention_backend: "auto", head_chunks: 0, ffn_chunks: 0, ffn_sequence_threshold: 4096 }));
  const note = el("div", "h3rt-expert-note");
  note.innerHTML = "Use these only to reproduce a backend or memory test. <strong>FFN chunking is no longer exposed here:</strong> Auto never selects it and attention is the useful H3 memory target.";
  grid.append(attentionField, headField, reset, note);
  root.append(summary, grid);
  if (advanced.attention_backend !== "auto" || Number(advanced.head_chunks) !== 0 || Number(advanced.ffn_chunks) !== 0) root.open = true;
  return root;
}

function buildSection(node) {
  const { state, preset, advanced } = runtimeState(node);
  if (String(state.ui?.director_node_id || "") !== String(node.id)) saveRuntime(node, state, preset, advanced, false);
  const section = el("section", "h3s-section h3s-runtime-section");
  const header = el("div", "h3s-section-header");
  header.append(el("span", "h3s-section-title", "Runtime"), el("span", "h3s-status-pill", preset === "auto" ? "AUTO" : "MANUAL"));
  const body = el("div", "h3s-section-stack h3rt");

  const intro = el("div", "h3rt-copy");
  const copy = el("p", "", "Changes kernels and memory behavior only. Sampling Profile, steps, LightX/PDD and LoRAs stay exactly as selected.");
  const detect = el("button", "h3rt-detect", "Detect hardware"); detect.type = "button";
  detect.addEventListener("click", async () => {
    detect.disabled = true;
    detect.textContent = "Detecting…";
    try { await loadCapabilities(true); node.__h3studioRuntimeCapabilityError = ""; }
    catch (error) { node.__h3studioRuntimeCapabilityError = String(error?.message || error); }
    installRuntimeSection(node, true);
  });
  intro.append(copy, detect);

  const presets = el("div", "h3rt-presets");
  for (const item of PRESETS.slice(0, 4)) presets.append(presetButton(node, ...item, preset === item[0]));
  const more = el("div", "h3rt-more");
  for (const item of PRESETS.slice(4)) more.append(presetButton(node, ...item, preset === item[0], true));
  presets.append(more);

  const status = el("div", "h3rt-status");
  if (capabilities) {
    status.append(
      chip("GPU", `${capabilities.gpu_name} · ${vram(capabilities.total_vram_gb)}`, capabilities.compute_capability || ""),
      chip("Fast path", `Comfy Kitchen ${bool(capabilities.ck_attention)}`),
      chip("Memory path", `Head chunks ${bool(capabilities.low_vram_attention)} · Sage ${bool(capabilities.sage_mem_eff)}`),
    );
  } else {
    status.append(chip("Hardware", node.__h3studioRuntimeCapabilityError || "Detecting GPU and installed attention backends…"));
    loadCapabilities().then(() => installRuntimeSection(node, true)).catch((error) => {
      node.__h3studioRuntimeCapabilityError = String(error?.message || error);
      installRuntimeSection(node, true);
    });
  }

  body.append(intro, presets, status, actualResult(node, preset), expert(node, state, preset, advanced));
  section.append(header, body);
  return section;
}

function sectionHost(panel) {
  return panel?.querySelector?.(".h3s-v7-inspector") || panel;
}

function installRuntimeSection(node, replace = false) {
  const panel = node?.__h3studioPanel;
  if (!panel?.isConnected) return;
  const existing = panel.querySelector(".h3s-runtime-section");
  if (existing && !replace) return;
  const section = buildSection(node);
  if (existing) existing.replaceWith(section);
  else {
    const host = sectionHost(panel);
    const loras = host.querySelector(".h3s-custom-loras");
    const fallback = [...host.children].find((child) => child.querySelector?.(".h3s-advanced-toggle"));
    host.insertBefore(section, loras || fallback || null);
  }
}

function watchDirector(node) {
  const wait = () => {
    if (!node.graph) return;
    if (node.__h3studioPanel?.isConnected) { installRuntimeSection(node); return; }
    setTimeout(wait, 50);
  };
  setTimeout(wait, 0);
}

api.addEventListener("h3studio-runtime-resolved", ({ detail }) => {
  const id = String(detail?.node_id || "");
  if (!id) return;
  for (const node of app.graph?._nodes || []) {
    if (node?.comfyClass !== TARGET || String(node.id) !== id) continue;
    node.__h3studioRuntimeResolved = detail;
    installRuntimeSection(node, true);
  }
});

app.registerExtension({
  name: "H3Studio.RuntimeOptimizationV4",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== TARGET) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function h3rtCreated() {
      const result = created?.apply(this, arguments);
      installStyles(); watchDirector(this); return result;
    };
    const configured = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function h3rtConfigured() {
      const result = configured?.apply(this, arguments);
      installStyles(); watchDirector(this); return result;
    };
  },
});
