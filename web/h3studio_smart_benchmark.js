import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { stateFromNode } from "./js/studio_extension.js";

const TARGET = "H3StudioSmartBenchmark";
const DIRECTOR = "H3StudioDirector";
const LOADER = "H3StudioLoader";
const ASSET_URL = "/h3studio/assets";
const STYLE_ID = "h3studio-smart-benchmark-v7-style";
const SHARE_PREFIX = "H3B1:";
const SHARE_ZIP_PREFIX = "H3B1Z:";
const WIDGET_NAME = "h3studio_smart_benchmark";

let catalog = null;
let catalogPromise = null;

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== "") node.textContent = String(text);
  return node;
}

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .h3b7{
      --b-bg:#2a2d32;--b-panel:#30343a;--b-panel2:#373b42;--b-border:#484d56;--b-border-soft:#3c4148;
      --b-text:#f2f3f5;--b-muted:#aab0b9;--b-muted2:#828993;--b-accent:#91a7c7;
      width:100%;max-width:100%;max-height:560px;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:stable;
      border:1px solid var(--b-border);border-radius:10px;background:var(--b-bg);color:var(--b-text);
      font:11px/1.4 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;box-sizing:border-box;contain:layout paint;
    }
    .h3b7 *{box-sizing:border-box;min-width:0}.h3b7::-webkit-scrollbar{width:9px}.h3b7::-webkit-scrollbar-thumb{background:#555b64;border:2px solid #2a2d32;border-radius:999px}
    .h3b7-top{position:sticky;top:0;z-index:8;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:11px 12px;background:#30343a;border-bottom:1px solid var(--b-border-soft)}
    .h3b7-title-row{display:flex;align-items:center;gap:8px}.h3b7-icon{display:grid;place-items:center;width:22px;height:22px;border-radius:6px;background:#444952;color:#f5f6f7;font-weight:800;font-size:9px}.h3b7-title{font-size:12px;font-weight:750}.h3b7-sub{margin-top:1px;color:var(--b-muted2);font-size:8.5px}.h3b7-assets{flex:none;padding:4px 7px;border:1px solid #515761;border-radius:5px;background:#393d44;color:#d7dbe0;font-size:8px;cursor:pointer}.h3b7-assets.error{color:#efb5ba;border-color:#75535a}
    .h3b7-body{padding:11px 12px 12px}.h3b7-toolbar{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:9px}.h3b7-segments{display:flex;gap:3px;flex-wrap:wrap;padding:3px;border-radius:7px;background:#25282d}.h3b7-segment{min-height:27px;padding:5px 8px;border:0;border-radius:5px;background:transparent;color:#aeb4bd;cursor:pointer;font:650 8.5px/1.2 inherit}.h3b7-segment:hover{background:#373b42;color:#fff}.h3b7-segment.is-active{background:#48515e;color:#fff}
    .h3b7-actions{display:flex;gap:4px;flex-wrap:wrap}.h3b7-btn{min-height:27px;padding:5px 8px;border:1px solid #4b5059;border-radius:5px;background:#373b42;color:#e1e4e8;cursor:pointer;font:650 8.5px/1.2 inherit}.h3b7-btn:hover{background:#40454d;border-color:#5b616b}.h3b7-btn.primary{background:#46505e;border-color:#647287;color:#fff}.h3b7-btn.danger{color:#e6a5ab}.h3b7-btn:disabled{opacity:.4;cursor:default}
    .h3b7-summary{display:flex;justify-content:space-between;gap:8px;padding:6px 8px;margin-bottom:7px;border-radius:5px;background:#34383e;color:#949ba4;font-size:8.5px}.h3b7-summary strong{color:#d7dbe0;font-weight:650}
    .h3b7-import{display:none;grid-template-columns:minmax(0,1fr) auto;gap:5px;margin-bottom:7px}.h3b7-import.open{display:grid}.h3b7-import textarea{min-height:54px;resize:vertical;border:1px solid #4b5059;border-radius:6px;background:#34383e;color:#f2f3f5;padding:6px 7px;font:8px/1.35 ui-monospace,SFMono-Regular,Consolas,monospace}
    .h3b7-list{display:flex;flex-direction:column;gap:6px}.h3b7-empty{padding:18px;border:1px dashed #4b5059;border-radius:7px;color:#949ba4;text-align:center;font-size:9px;background:#2e3136}
    .h3b7-scenario{border:1px solid #454a52;border-radius:7px;background:#30343a;overflow:hidden}.h3b7-scenario[open]{border-color:#555c66}.h3b7-scenario>summary{display:grid;grid-template-columns:24px minmax(0,1fr) auto auto auto 22px;align-items:center;gap:6px;min-height:40px;padding:6px 8px;list-style:none;cursor:pointer}.h3b7-scenario>summary::-webkit-details-marker{display:none}.h3b7-index{display:grid;place-items:center;width:22px;height:22px;border-radius:5px;background:#41464d;color:#d7dbe0;font-weight:750;font-size:8.5px}.h3b7-name{height:28px;border:1px solid transparent;border-radius:5px;background:transparent;color:#f2f3f5;padding:4px 6px;font:700 9.5px/1.2 inherit}.h3b7-name:hover,.h3b7-name:focus{outline:none;border-color:#505660;background:#393d43}.h3b7-tag{max-width:125px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:3px 6px;border-radius:4px;background:#3b4047;color:#b9c0c8;font-size:7.5px}.h3b7-caret{color:#969da7;transition:transform .12s}.h3b7-scenario[open] .h3b7-caret{transform:rotate(90deg)}
    .h3b7-fields{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr) minmax(0,1fr) 86px;gap:7px;padding:9px 9px 8px;border-top:1px solid #40454c;background:#2d3035}.h3b7-field{display:flex;flex-direction:column;gap:3px}.h3b7-label{color:#949ba4;font-size:7.5px;font-weight:650;text-transform:uppercase;letter-spacing:.05em}.h3b7-input,.h3b7-select{width:100%;height:29px;border:1px solid #4b5059;border-radius:5px;background:#383c42;color:#f0f2f4;padding:4px 7px;font:8.5px/1.2 inherit}.h3b7-input:focus,.h3b7-select:focus{outline:none;border-color:#71829a;box-shadow:0 0 0 2px rgba(145,167,199,.09)}
    .h3b7-loras{grid-column:1/-1;margin-top:1px}.h3b7-loras>summary{cursor:pointer;color:#aeb4bd;font-size:8.5px;list-style:none}.h3b7-loras>summary::-webkit-details-marker{display:none}.h3b7-loras>summary::before{content:'›';display:inline-block;width:14px;color:#8e96a0}.h3b7-loras[open]>summary::before{transform:rotate(90deg)}.h3b7-lora-body{display:flex;flex-direction:column;gap:4px;margin-top:6px}.h3b7-lora{display:grid;grid-template-columns:minmax(0,1fr) 70px 24px;gap:5px;align-items:center;padding:5px 6px;border-radius:5px;background:#373b42}.h3b7-lora-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:8px/1.2 ui-monospace,SFMono-Regular,Consolas,monospace}.h3b7-strength{height:25px;border:1px solid #4b5059;border-radius:5px;background:#30343a;color:#f1f2f4;padding:3px 5px;font-size:8px}.h3b7-x{width:24px;height:24px;border:0;border-radius:4px;background:transparent;color:#d99aa0;cursor:pointer}.h3b7-x:hover{background:#4a3a3d}.h3b7-add{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px}
    @container (max-width:650px){.h3b7-fields{grid-template-columns:1fr 1fr}.h3b7-scenario>summary{grid-template-columns:22px minmax(0,1fr) auto 22px}.h3b7-scenario>summary .h3b7-tag:nth-of-type(n+2){display:none}}
    @container (max-width:470px){.h3b7-fields{grid-template-columns:1fr}.h3b7-top{align-items:flex-start;flex-direction:column}.h3b7-toolbar{align-items:flex-start;flex-direction:column}.h3b7-scenario>summary{grid-template-columns:22px minmax(0,1fr) 22px}.h3b7-tag{display:none}}
  `;
  document.head.append(style);
}

function widget(node, name) { return node?.widgets?.find((item) => item.name === name) || null; }
function graphLink(id) {
  const links = app.graph?.links;
  if (!links || id == null) return null;
  return typeof links.get === "function" ? links.get(id) : links[id];
}
function sourceNode(node, inputName, expectedClass = "") {
  const input = node?.inputs?.find((item) => item.name === inputName);
  const link = graphLink(input?.link);
  if (!link) return null;
  const source = app.graph?.getNodeById?.(Number(link.origin_id ?? link.originId ?? link.source_id));
  return !expectedClass || source?.comfyClass === expectedClass ? source : null;
}
function routeFor(director) {
  const state = director ? stateFromNode(director) : null;
  if (state?.generation?.route === "ref2va") return "ref2va";
  if (state?.generation?.route === "fl2va") return "fl2va";
  const refs = (state?.references || []).filter((item) => item?.enabled !== false).length;
  if (state?.generation?.mode === "reference_edit" || refs >= 2 || String(state?.generation?.sampling_profile || "").startsWith("pdd_ref2va_")) return "ref2va";
  return "fl2va";
}
function currentScenario(node, name = "Current setup") {
  const director = sourceNode(node, "studio_context", DIRECTOR);
  const loader = sourceNode(node, "h3_bundle", LOADER);
  const state = director ? stateFromNode(director) : {};
  const route = routeFor(director);
  return {
    name,
    model_name: String(widget(loader, route === "ref2va" ? "ref2va_model" : "fl2va_model")?.value || ""),
    sampling_profile: state?.generation?.sampling_profile || "base_quality_20",
    runtime_preset: state?.ui?.runtime_optimization || "auto",
    runtime_advanced: structuredClone(state?.ui?.runtime_advanced || {}),
    megapixels: Number(state?.generation?.megapixels || 1),
    custom_loras: structuredClone(Array.isArray(state?.ui?.custom_loras) ? state.ui.custom_loras : []),
  };
}
function parseScenarios(node) {
  try {
    const value = JSON.parse(String(widget(node, "scenarios_json")?.value || "[]"));
    return Array.isArray(value) ? value : [];
  } catch { return []; }
}
function saveScenarios(node, scenarios, preset = "custom") {
  const target = widget(node, "scenarios_json");
  if (!target) return;
  target.value = JSON.stringify(scenarios);
  target.callback?.(target.value, app.canvas, node, [0, 0], {});
  node.properties ||= {};
  node.properties.h3studio_benchmark_preset = preset;
  node.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}
function hideNativeWidget(target) {
  if (!target) return;
  target.hidden = true;
  target.__h3b7OriginalCompute ||= target.computeSize;
  target.computeSize = () => [0, 0];
  target.type = "hidden";
}
function hidePlumbing(node) {
  for (const name of ["scenarios_json", "max_scenarios", "grid_cell_size"]) hideNativeWidget(widget(node, name));
}

async function loadCatalog(force = false) {
  if (!force && catalog) return catalog;
  if (!force && catalogPromise) return catalogPromise;
  catalogPromise = (async () => {
    const response = await api.fetchApi(ASSET_URL, { cache: "no-store" });
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = null; }
    if (!response.ok || data?.error) throw new Error(data?.error || `HTTP ${response.status}`);
    catalog = data;
    return data;
  })();
  try { return await catalogPromise; } finally { catalogPromise = null; }
}
function modelChoices(route) {
  return (catalog?.models || []).filter((item) => item.route === route || item.route === "unknown").map((item) => item.name);
}
function samplingChoices(route) {
  return (catalog?.sampling_profiles || []).filter((item) => !item.route || item.route === route).map((item) => [item.key, item.label || item.key]);
}
function runtimeChoices() {
  const source = catalog?.runtime_presets || [];
  return source.length ? source.map((item) => [item.key, item.key === "og_current" ? "OG" : (item.label || item.key)]) : [
    ["auto", "Auto"], ["fast", "Fast"], ["og_current", "OG"], ["quality", "Quality"], ["low_vram", "Low VRAM"], ["extreme_low_vram", "Extreme"],
  ];
}
function installedLoras() { return (catalog?.loras || []).filter((item) => item.known_h3).map((item) => item.name); }

function applyPreset(node, kind) {
  const base = currentScenario(node);
  let scenarios;
  if (kind === "current") scenarios = [base];
  else if (kind === "auto-og") scenarios = [
    { ...structuredClone(base), name: "Auto", runtime_preset: "auto" },
    { ...structuredClone(base), name: "OG", runtime_preset: "og_current" },
  ];
  else if (kind === "runtime") scenarios = [
    { ...structuredClone(base), name: "Auto", runtime_preset: "auto" },
    { ...structuredClone(base), name: "Fast", runtime_preset: "fast" },
    { ...structuredClone(base), name: "OG", runtime_preset: "og_current" },
  ];
  else scenarios = [
    { ...structuredClone(base), name: "Auto", runtime_preset: "auto" },
    { ...structuredClone(base), name: "Low VRAM", runtime_preset: "low_vram" },
    { ...structuredClone(base), name: "Extreme", runtime_preset: "extreme_low_vram" },
  ];
  saveScenarios(node, scenarios, kind);
  render(node);
}
function patchScenario(node, index, patch) {
  const scenarios = parseScenarios(node);
  if (!scenarios[index]) return;
  scenarios[index] = { ...scenarios[index], ...patch };
  saveScenarios(node, scenarios, "custom");
  render(node);
}
function removeScenario(node, index) {
  const scenarios = parseScenarios(node);
  scenarios.splice(index, 1);
  saveScenarios(node, scenarios, "custom");
  render(node);
}

function selectInput(options, value, onChange, label) {
  const select = el("select", "h3b7-select");
  select.setAttribute("aria-label", label);
  for (const [key, text] of options) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = text;
    option.selected = String(key) === String(value);
    select.append(option);
  }
  select.addEventListener("change", () => onChange(select.value));
  return select;
}
function field(label, control) {
  const root = el("label", "h3b7-field");
  root.append(el("span", "h3b7-label", label), control);
  return root;
}

function loraEditor(node, scenario, index) {
  const values = Array.isArray(scenario.custom_loras) ? scenario.custom_loras : [];
  const details = el("details", "h3b7-loras");
  const summary = el("summary", "", `LoRAs${values.length ? ` · ${values.length}` : ""}`);
  const body = el("div", "h3b7-lora-body");
  values.forEach((item, loraIndex) => {
    if (!item?.name) return;
    const row = el("div", "h3b7-lora");
    const name = el("div", "h3b7-lora-name", item.name); name.title = item.name;
    const strength = el("input", "h3b7-strength"); strength.type = "number"; strength.step = "0.05"; strength.min = "-4"; strength.max = "4"; strength.value = String(item.strength ?? 1);
    strength.addEventListener("change", () => {
      const next = structuredClone(values); next[loraIndex] = { ...next[loraIndex], strength: Number(strength.value) || 0 }; patchScenario(node, index, { custom_loras: next });
    });
    const remove = el("button", "h3b7-x", "×"); remove.type = "button"; remove.title = "Remove LoRA";
    remove.addEventListener("click", (event) => { event.preventDefault(); const next = structuredClone(values); next.splice(loraIndex, 1); patchScenario(node, index, { custom_loras: next }); });
    row.append(name, strength, remove); body.append(row);
  });
  const add = el("div", "h3b7-add");
  const search = el("input", "h3b7-input"); search.placeholder = "Search installed H3 LoRA…"; search.setAttribute("list", `h3b7-loras-${node.id}-${index}`);
  const list = el("datalist"); list.id = `h3b7-loras-${node.id}-${index}`;
  for (const name of installedLoras()) { const option = document.createElement("option"); option.value = name; list.append(option); }
  const button = el("button", "h3b7-btn", "Add"); button.type = "button";
  button.addEventListener("click", (event) => {
    event.preventDefault(); const name = search.value.trim(); if (!name) return;
    const next = structuredClone(values); next.push({ name, strength: 1, enabled: true }); patchScenario(node, index, { custom_loras: next });
  });
  add.append(search, button, list); body.append(add); details.append(summary, body); return details;
}

function scenarioRow(node, scenario, index, route, scenarioCount) {
  const details = el("details", "h3b7-scenario");
  if (index === 0 || scenarioCount <= 2) details.open = true;
  const summary = el("summary");
  const name = el("input", "h3b7-name"); name.value = scenario.name || `Scenario ${index + 1}`; name.setAttribute("aria-label", `Scenario ${index + 1} name`);
  name.addEventListener("click", (event) => event.stopPropagation());
  name.addEventListener("change", () => patchScenario(node, index, { name: name.value.trim() || `Scenario ${index + 1}` }));
  const runtimeLabel = runtimeChoices().find(([key]) => key === String(scenario.runtime_preset || "auto"))?.[1] || String(scenario.runtime_preset || "Auto");
  const samplingLabel = samplingChoices(route).find(([key]) => key === String(scenario.sampling_profile || ""))?.[1] || String(scenario.sampling_profile || "Sampling");
  const remove = el("button", "h3b7-x", "×"); remove.type = "button"; remove.title = "Remove scenario"; remove.addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); removeScenario(node, index); });
  summary.append(
    el("span", "h3b7-index", index + 1), name,
    el("span", "h3b7-tag", runtimeLabel), el("span", "h3b7-tag", samplingLabel),
    el("span", "h3b7-tag", `${Number(scenario.megapixels || 1).toFixed(2)} MP`),
    remove,
  );

  const model = el("input", "h3b7-input"); model.value = scenario.model_name || ""; model.placeholder = "Installed transformer…"; model.setAttribute("list", `h3b7-models-${node.id}-${index}`);
  const models = el("datalist"); models.id = `h3b7-models-${node.id}-${index}`;
  for (const choice of modelChoices(route)) { const option = document.createElement("option"); option.value = choice; models.append(option); }
  model.addEventListener("change", () => patchScenario(node, index, { model_name: model.value.trim() }));
  const modelWrap = field("Transformer", model); modelWrap.append(models);

  const sampling = selectInput(samplingChoices(route), scenario.sampling_profile, (value) => patchScenario(node, index, { sampling_profile: value }), "Sampling profile");
  const runtime = selectInput(runtimeChoices(), scenario.runtime_preset || "auto", (value) => patchScenario(node, index, { runtime_preset: value }), "Runtime preset");
  const mp = el("input", "h3b7-input"); mp.type = "number"; mp.min = "0.2"; mp.max = "8.5"; mp.step = "0.05"; mp.value = String(Number(scenario.megapixels || 1)); mp.addEventListener("change", () => patchScenario(node, index, { megapixels: Number(mp.value) || 1 }));
  const fields = el("div", "h3b7-fields");
  fields.append(modelWrap, field("Sampling", sampling), field("Runtime", runtime), field("MP", mp), loraEditor(node, scenario, index));
  details.append(summary, fields);
  return details;
}

function bytesToB64(bytes) { let value = ""; for (const byte of bytes) value += String.fromCharCode(byte); return btoa(value); }
function b64ToBytes(value) { const raw = atob(value); return Uint8Array.from(raw, (char) => char.charCodeAt(0)); }
async function gzipBytes(bytes) {
  if (typeof CompressionStream !== "function") return null;
  const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}
async function gunzipBytes(bytes) {
  if (typeof DecompressionStream !== "function") throw new Error("This browser cannot unpack compressed benchmark codes.");
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}
async function exportCode(node) {
  const raw = new TextEncoder().encode(JSON.stringify({ v: 1, scenarios: parseScenarios(node) }));
  const plain = `${SHARE_PREFIX}${bytesToB64(raw)}`;
  const zipped = await gzipBytes(raw);
  if (!zipped) return plain;
  const compact = `${SHARE_ZIP_PREFIX}${bytesToB64(zipped)}`;
  return compact.length < plain.length ? compact : plain;
}
async function importCode(raw) {
  const text = String(raw || "").trim();
  const start = [SHARE_ZIP_PREFIX, SHARE_PREFIX].map((prefix) => [prefix, text.indexOf(prefix)]).filter(([, index]) => index >= 0).sort((a, b) => a[1] - b[1])[0];
  const code = start ? text.slice(start[1]).split(/\s/)[0] : text;
  let payload;
  if (code.startsWith(SHARE_ZIP_PREFIX)) payload = JSON.parse(new TextDecoder().decode(await gunzipBytes(b64ToBytes(code.slice(SHARE_ZIP_PREFIX.length)))));
  else if (code.startsWith(SHARE_PREFIX)) payload = JSON.parse(new TextDecoder().decode(b64ToBytes(code.slice(SHARE_PREFIX.length))));
  else payload = JSON.parse(code);
  if (Number(payload?.v) !== 1 || !Array.isArray(payload.scenarios)) throw new Error("Unsupported H3 benchmark preset.");
  return payload.scenarios;
}
async function copyText(text) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  const area = el("textarea"); area.value = text; area.style.position = "fixed"; area.style.opacity = "0"; document.body.append(area); area.select(); document.execCommand("copy"); area.remove();
}
function toast(summary, detail, severity = "success") { app.extensionManager?.toast?.add?.({ severity, summary, detail, life: 4200 }); }

function buildRoot(node) {
  const root = el("div", "h3b7"); root.dataset.h3BenchmarkUi = "v7";
  const director = sourceNode(node, "studio_context", DIRECTOR);
  const route = routeFor(director);
  const scenarios = parseScenarios(node);

  const top = el("div", "h3b7-top");
  const titleRow = el("div", "h3b7-title-row");
  titleRow.append(el("span", "h3b7-icon", "AB"), el("div", "", ""));
  titleRow.lastChild.append(el("div", "h3b7-title", "Smart Benchmark"), el("div", "h3b7-sub", "Compare runtime, sampling, model or LoRA changes with the same Director seed."));
  const assets = el("button", "h3b7-assets", catalog ? `${catalog.models?.length || 0} models · ${catalog.loras?.length || 0} LoRAs` : "Checking assets…"); assets.type = "button"; assets.title = "Refresh installed assets";
  assets.addEventListener("click", async () => { catalog = null; try { await loadCatalog(true); node.__h3b7AssetError = ""; } catch (error) { node.__h3b7AssetError = String(error?.message || error); } render(node); });
  if (node.__h3b7AssetError) { assets.classList.add("error"); assets.textContent = "Assets unavailable"; assets.title = node.__h3b7AssetError; }
  top.append(titleRow, assets); root.append(top);

  const body = el("div", "h3b7-body");
  const toolbar = el("div", "h3b7-toolbar");
  const segments = el("div", "h3b7-segments");
  const active = String(node.properties?.h3studio_benchmark_preset || "custom");
  for (const [key, label] of [["current", "Current"], ["auto-og", "Auto vs OG"], ["runtime", "Runtime"], ["memory", "Memory"]]) {
    const button = el("button", `h3b7-segment${active === key ? " is-active" : ""}`, label); button.type = "button"; button.addEventListener("click", () => applyPreset(node, key)); segments.append(button);
  }
  const actions = el("div", "h3b7-actions");
  const add = el("button", "h3b7-btn primary", "+ Scenario"); add.type = "button"; add.addEventListener("click", () => { const next = [...parseScenarios(node), currentScenario(node, `Scenario ${parseScenarios(node).length + 1}`)]; saveScenarios(node, next, "custom"); render(node); });
  const copy = el("button", "h3b7-btn", "Copy preset"); copy.type = "button"; copy.addEventListener("click", async () => { const code = await exportCode(node); await copyText(`H3 Studio benchmark · ${parseScenarios(node).length} scenarios\n${code}`); toast("Benchmark preset copied", `${code.length} characters`); });
  const paste = el("button", "h3b7-btn", "Import"); paste.type = "button"; paste.addEventListener("click", () => root.querySelector(".h3b7-import")?.classList.toggle("open"));
  const clear = el("button", "h3b7-btn", "Clear"); clear.type = "button"; clear.addEventListener("click", () => { saveScenarios(node, [], "custom"); render(node); });
  actions.append(add, copy, paste, clear); toolbar.append(segments, actions); body.append(toolbar);

  const importer = el("div", "h3b7-import");
  const area = el("textarea"); area.placeholder = "Paste H3B1 / H3B1Z code or benchmark JSON…";
  const importButton = el("button", "h3b7-btn primary", "Import"); importButton.type = "button"; importButton.addEventListener("click", async () => { try { saveScenarios(node, await importCode(area.value), "custom"); render(node); toast("Benchmark imported", "Scenario state restored."); } catch (error) { toast("Benchmark import failed", String(error?.message || error), "error"); } });
  importer.append(area, importButton); body.append(importer);

  const max = Number(widget(node, "max_scenarios")?.value || 12);
  const summary = el("div", "h3b7-summary"); summary.append(el("span", "", `${scenarios.length} scenario${scenarios.length === 1 ? "" : "s"} · ${route.toUpperCase()} · same seed`), el("strong", "", scenarios.length > max ? `Over guard ${max}` : `Guard ${max}`)); body.append(summary);
  const list = el("div", "h3b7-list");
  if (!scenarios.length) list.append(el("div", "h3b7-empty", "Choose a comparison above or add the current setup."));
  scenarios.forEach((scenario, index) => list.append(scenarioRow(node, scenario, index, route, scenarios.length)));
  body.append(list); root.append(body);
  return root;
}

function render(node) {
  hidePlumbing(node);
  const root = node?.__h3bRoot;
  if (!node?.graph || !root?.isConnected) return;
  const next = buildRoot(node);
  root.className = next.className;
  root.dataset.h3BenchmarkUi = "v7";
  root.replaceChildren(...Array.from(next.childNodes));
  node.setDirtyCanvas?.(true, true);
}

function dedupeDomWidgets(node) {
  const matches = (node.widgets || []).filter((item) => item.name === WIDGET_NAME);
  if (matches.length <= 1) return matches[0] || null;
  const keep = matches[0];
  for (const extra of matches.slice(1)) {
    extra.element?.remove?.(); extra.inputEl?.remove?.();
    const index = node.widgets.indexOf(extra); if (index >= 0) node.widgets.splice(index, 1);
  }
  return keep;
}

function install(node) {
  installStyles(); hidePlumbing(node); dedupeDomWidgets(node);
  node.color = "#3a3e45";
  node.bgcolor = "#272a2f";
  if (node.__h3bInstalled && node.__h3bRoot?.isConnected) { render(node); return; }
  if (typeof node.addDOMWidget !== "function") return;
  node.__h3bInstalled = true;
  const existing = dedupeDomWidgets(node);
  if (existing?.element?.isConnected) {
    node.__h3bRoot = existing.element; render(node);
  } else {
    const root = buildRoot(node); node.__h3bRoot = root;
    const domWidget = node.addDOMWidget(WIDGET_NAME, WIDGET_NAME, root, {
      serialize: false,
      hideOnZoom: true,
      getValue: () => undefined,
      getMinHeight: () => 330,
      getMaxHeight: () => 560,
    });
    if (domWidget) { domWidget.hideOnZoom = true; domWidget.options ||= {}; domWidget.options.hideOnZoom = true; }
  }
  const width = Math.max(760, Number(node.size?.[0]) || 760);
  const height = Math.max(540, Math.min(680, Number(node.size?.[1]) || 600));
  node.setSize?.([width, height]);
  loadCatalog().then(() => { node.__h3b7AssetError = ""; render(node); }).catch((error) => { node.__h3b7AssetError = String(error?.message || error); render(node); });
}

app.registerExtension({
  name: "H3Studio.SmartBenchmarkUIV7",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== TARGET) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function h3b7Created() { const result = created?.apply(this, arguments); queueMicrotask(() => install(this)); return result; };
    const configured = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function h3b7Configured() { const result = configured?.apply(this, arguments); queueMicrotask(() => install(this)); return result; };
  },
  afterConfigureGraph() {
    setTimeout(() => { for (const node of app.graph?._nodes || []) if (node?.comfyClass === TARGET) install(node); }, 80);
  },
});
