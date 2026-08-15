import { app } from "../../scripts/app.js";
import { applyState, stateFromNode } from "./js/studio_extension.js";

const TARGET = "H3StudioDirector";
const LOADER = "H3StudioLoader";
const PREFIX = "H3S1:";
const ZIP_PREFIX = "H3S1Z:";
const STYLE_ID = "h3studio-share-style";

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .h3s-share-body { display:flex; flex-direction:column; gap:8px; }
    .h3s-share-actions { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:6px; }
    .h3s-share-button { border:1px solid var(--h3s-border,#4a4f57); background:var(--h3s-panel-2,#363a40); color:inherit; border-radius:6px; padding:6px 8px; cursor:pointer; font:inherit; min-width:0; }
    .h3s-share-button.primary { border-color:color-mix(in srgb,var(--h3s-accent,#91a7c7) 55%,var(--h3s-border,#4a4f57)); }
    .h3s-share-button:hover { border-color:var(--h3s-accent,#91a7c7); }
    .h3s-share-meta { font-size:9px; opacity:.65; line-height:1.4; }
    @media (max-width:560px) { .h3s-share-actions { grid-template-columns:1fr; } }
  `;
  document.head.append(style);
}

function widget(node, name) {
  return node?.widgets?.find((candidate) => candidate.name === name) || null;
}

function graphLink(id) {
  const links = app.graph?.links;
  if (!links || id == null) return null;
  return typeof links.get === "function" ? links.get(id) : links[id];
}

function connectedLoader(node) {
  const input = node?.inputs?.find((candidate) => candidate.name === "h3_bundle");
  const link = graphLink(input?.link);
  if (!link) return null;
  const sourceId = link.origin_id ?? link.originId ?? link.source_id;
  const source = app.graph?.getNodeById?.(Number(sourceId));
  return source?.comfyClass === LOADER ? source : null;
}

function loaderAssets(node) {
  const loader = connectedLoader(node);
  if (!loader) return {};
  const names = ["fl2va_model", "ref2va_model", "text_encoder", "video_vae", "image_vae", "image_analyzer", "prompt_writer"];
  return Object.fromEntries(names.map((name) => [name, String(widget(loader, name)?.value || "")]).filter(([, value]) => value));
}

function compactPreset(node) {
  const state = stateFromNode(node);
  const g = state.generation || {};
  const p = state.prompt_options || {};
  const ui = state.ui || {};
  return {
    v: 1,
    g: {
      mode: g.mode, route: g.route, aspect_ratio: g.aspect_ratio, megapixels: g.megapixels,
      custom_width: g.custom_width, custom_height: g.custom_height,
      sampling_profile: g.sampling_profile, frame_profile: g.frame_profile,
      cap_native_resolution: Boolean(g.cap_native_resolution),
    },
    p: {
      enhance_mode: p.enhance_mode, analyze_images: Boolean(p.analyze_images),
      deep_enhancement: Boolean(p.deep_enhancement), adherence: p.adherence,
      detail_level: p.detail_level, analyzer_resolution: p.analyzer_resolution,
    },
    r: {
      preset: String(ui.runtime_optimization || "auto"),
      advanced: ui.runtime_advanced || {},
    },
    l: Array.isArray(ui.custom_loras) ? ui.custom_loras.map((item) => ({
      name: String(item?.name || ""), strength: Number(item?.strength ?? 1), enabled: item?.enabled !== false,
    })).filter((item) => item.name) : [],
    a: loaderAssets(node),
  };
}

function bytesToBase64Url(bytes) {
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/g, "");
}

function base64UrlToBytes(value) {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  const padded = normalized + "=".repeat((4 - normalized.length % 4) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

async function gzipBytes(bytes) {
  if (typeof CompressionStream !== "function") return null;
  const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function gunzipBytes(bytes) {
  if (typeof DecompressionStream !== "function") throw new Error("This browser cannot unpack compressed H3S presets. Update the ComfyUI browser/frontend.");
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function encodePreset(node) {
  const raw = new TextEncoder().encode(JSON.stringify(compactPreset(node)));
  const normal = `${PREFIX}${bytesToBase64Url(raw)}`;
  const zipped = await gzipBytes(raw);
  if (!zipped) return normal;
  const compact = `${ZIP_PREFIX}${bytesToBase64Url(zipped)}`;
  return compact.length < normal.length ? compact : normal;
}

function extractShareCode(text) {
  const candidates = [ZIP_PREFIX, PREFIX]
    .map((prefix) => ({ prefix, index: text.indexOf(prefix) }))
    .filter((item) => item.index >= 0)
    .sort((a, b) => a.index - b.index);
  if (!candidates.length) return "";
  const match = candidates[0];
  return text.slice(match.index).split(/\s/)[0];
}

async function decodePreset(raw) {
  const text = String(raw || "").trim();
  const code = extractShareCode(text);
  let value;
  if (code.startsWith(ZIP_PREFIX)) {
    const unpacked = await gunzipBytes(base64UrlToBytes(code.slice(ZIP_PREFIX.length)));
    value = JSON.parse(new TextDecoder().decode(unpacked));
  } else if (code.startsWith(PREFIX)) {
    value = JSON.parse(new TextDecoder().decode(base64UrlToBytes(code.slice(PREFIX.length))));
  } else {
    value = JSON.parse(text);
  }
  if (!value || Number(value.v || 0) !== 1) throw new Error("Unsupported H3 Studio preset version.");
  return value;
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.append(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}

function toast(summary, detail, severity = "success") {
  app.extensionManager?.toast?.add?.({ severity, summary, detail, life: 4500 });
}

function widgetChoices(target) {
  if (!target) return null;
  let values = target.options?.values;
  if (typeof values === "function") {
    try { values = values(); } catch { values = null; }
  }
  if (!Array.isArray(values)) return null;
  return values.map((value) => String(value));
}

function setLoaderAssets(node, assets) {
  const loader = connectedLoader(node);
  if (!loader || !assets || typeof assets !== "object") return { loader: false, changed: 0, missing: [] };
  let changed = 0;
  const missing = [];
  for (const [name, value] of Object.entries(assets)) {
    if (!value) continue;
    const target = widget(loader, name);
    if (!target || target.value === value) continue;
    const choices = widgetChoices(target);
    if (choices && !choices.includes(String(value))) {
      missing.push(`${name}: ${value}`);
      continue;
    }
    target.value = value;
    target.callback?.(value, app.canvas, loader, [0, 0], {});
    changed += 1;
  }
  if (changed) loader.setDirtyCanvas?.(true, true);
  return { loader: true, changed, missing };
}

function applyPreset(node, preset) {
  const state = stateFromNode(node);
  const allowedG = ["mode", "route", "aspect_ratio", "megapixels", "custom_width", "custom_height", "sampling_profile", "frame_profile", "cap_native_resolution"];
  const allowedP = ["enhance_mode", "analyze_images", "deep_enhancement", "adherence", "detail_level", "analyzer_resolution"];
  state.generation = { ...(state.generation || {}) };
  state.prompt_options = { ...(state.prompt_options || {}) };
  for (const key of allowedG) if (preset.g?.[key] !== undefined) state.generation[key] = preset.g[key];
  for (const key of allowedP) if (preset.p?.[key] !== undefined) state.prompt_options[key] = preset.p[key];
  state.ui = {
    ...(state.ui || {}),
    runtime_optimization: String(preset.r?.preset || "auto"),
    runtime_advanced: preset.r?.advanced && typeof preset.r.advanced === "object" ? preset.r.advanced : {},
    custom_loras: Array.isArray(preset.l) ? preset.l : [],
  };
  applyState(node, state);
  return setLoaderAssets(node, preset.a);
}

function summaryLine(node) {
  const state = stateFromNode(node);
  const ui = state.ui || {};
  const loras = (ui.custom_loras || []).filter((item) => item?.enabled !== false && item?.name).length;
  const preset = String(ui.runtime_optimization || "auto") === "og_current" ? "OG" : String(ui.runtime_optimization || "auto").replaceAll("_", " ");
  return `H3 Studio · ${preset} · ${state.generation.sampling_profile} · ${Number(state.generation.megapixels || 0).toFixed(2)} MP · ${loras} custom LoRA${loras === 1 ? "" : "s"}`;
}

function effectiveText(node) {
  const data = node.__h3studioRuntimeResolved;
  if (!data) return "H3 Studio effective config is available after one generation.";
  const work = data.workload || {};
  const cap = data.capabilities || {};
  const assets = data.assets || {};
  const state = stateFromNode(node);
  const loras = (state.ui?.custom_loras || []).filter((item) => item?.enabled !== false && item?.name);
  return [
    `H3 Studio · ${data.requested_label} -> ${data.resolved_label}`,
    `GPU: ${cap.gpu_name || "unknown"} · ${Number(cap.total_vram_gb || 0).toFixed(1)} GB · ${cap.os_name || ""}`,
    `Workload: ${String(work.route || "").toUpperCase()} · ${work.frames || "?"}f · ${work.width || "?"}x${work.height || "?"} · ${Number(work.megapixels || 0).toFixed(2)} MP · ${Number(work.sequence_length || 0).toLocaleString()} packed tokens`,
    `Attention: ${data.attention_label || data.attention_backend} · head chunks ${Number(data.head_chunks) > 1 ? data.head_chunks : "off"}`,
    `Sampling: ${data.sampling_profile}`,
    `Model: ${assets.transformer || "unknown"}`,
    `Text encoder: ${assets.text_encoder || "unknown"}`,
    `LoRAs: ${loras.length ? loras.map((item) => `${item.name} @ ${Number(item.strength ?? 1).toFixed(2).replace(/\.?0+$/, "")}`).join(", ") : "none"}`,
    `Why: ${data.reason || ""}`,
  ].join("\n");
}

function button(text, title, click, primary = false) {
  const item = document.createElement("button");
  item.type = "button";
  item.className = `h3s-share-button${primary ? " primary" : ""}`;
  item.textContent = text;
  item.title = title;
  item.addEventListener("click", async (event) => {
    event.preventDefault(); event.stopPropagation();
    try { await click(); } catch (error) { toast("H3 Studio preset", String(error?.message || error), "error"); }
  });
  return item;
}

function buildSection(node) {
  const section = document.createElement("section");
  section.className = "h3s-section h3s-share-section";
  const header = document.createElement("div");
  header.className = "h3s-section-header";
  const title = document.createElement("span"); title.className = "h3s-section-title"; title.textContent = "Preset";
  header.append(title);
  const body = document.createElement("div"); body.className = "h3s-section-stack h3s-share-body";
  const help = document.createElement("p"); help.className = "h3s-context-help";
  help.textContent = "Portable H3S presets carry runtime, Sampling Profile, resolution, custom LoRAs + strengths and connected Loader model choices. Prompts and reference images are never included.";
  const actions = document.createElement("div"); actions.className = "h3s-share-actions";
  actions.append(
    button("Copy preset", "Copy a readable one-line summary plus the shortest supported H3S code", async () => {
      const code = await encodePreset(node);
      await copyText(`${summaryLine(node)}\n${code}`);
      toast("Preset copied", `${code.length} character ${code.startsWith(ZIP_PREFIX) ? "compressed " : ""}preset code`);
    }, true),
    button("Copy code", "Copy only the compact H3S preset code", async () => {
      const code = await encodePreset(node); await copyText(code); toast("Preset code copied", `${code.length} characters`);
    }),
    button("Import", "Paste an H3S1/H3S1Z code or JSON preset", async () => {
      const raw = globalThis.prompt?.("Paste H3S preset code or JSON:", "");
      if (!raw) return;
      const preset = await decodePreset(raw);
      const result = applyPreset(node, preset);
      const missing = result.missing || [];
      const detail = result.loader
        ? `Director restored · ${result.changed} Loader field${result.changed === 1 ? "" : "s"} updated${missing.length ? ` · ${missing.length} shared asset${missing.length === 1 ? "" : "s"} missing locally` : ""}`
        : "Director restored · connect H3 Studio Loader to apply shared model choices";
      toast("Preset imported", detail, !result.loader || missing.length ? "warn" : "success");
      if (missing.length) console.warn("[H3 Studio] Shared preset assets missing locally:\n" + missing.join("\n"));
      installShareSection(node, true);
    }),
    button("Copy run config", "Copy exactly what Auto resolved on the last completed generation", async () => {
      await copyText(effectiveText(node));
      toast("Run config copied", "Ready to paste into an issue or benchmark note.");
    }),
  );
  const meta = document.createElement("div"); meta.className = "h3s-share-meta";
  meta.textContent = "H3S1/H3S1Z is versioned and path-safe. Compression is automatic when it makes the preset shorter; older uncompressed H3S1 codes still import.";
  body.append(help, actions, meta);
  section.append(header, body);
  return section;
}

function sectionHost(panel) {
  return panel?.querySelector?.(".h3s-v7-inspector") || panel;
}

function installShareSection(node, replace = false) {
  const panel = node?.__h3studioPanel;
  if (!panel?.isConnected) return;
  const existing = panel.querySelector(".h3s-share-section");
  if (existing && !replace) return;
  const section = buildSection(node);
  if (existing) existing.replaceWith(section);
  else {
    const host = sectionHost(panel);
    const advanced = [...host.children].find((child) => child.querySelector?.(".h3s-advanced-toggle"));
    host.insertBefore(section, advanced || null);
  }
}

function watch(node) {
  const wait = () => {
    if (!node.graph) return;
    if (node.__h3studioPanel?.isConnected) { installShareSection(node); return; }
    setTimeout(wait, 70);
  };
  setTimeout(wait, 0);
}

app.registerExtension({
  name: "H3Studio.SharePreset",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== TARGET) return;
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function h3studioShareCreated() {
      const result = originalCreated?.apply(this, arguments);
      installStyles(); watch(this); return result;
    };
    const originalConfigured = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function h3studioShareConfigured() {
      const result = originalConfigured?.apply(this, arguments);
      installStyles(); watch(this); return result;
    };
  },
});
