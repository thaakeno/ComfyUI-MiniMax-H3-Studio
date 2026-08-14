import { app } from "../../scripts/app.js";
import { applyState, stateFromNode } from "./js/studio_extension.js";

const DIRECTOR = "H3StudioDirector";
const LOADER = "H3StudioLoader";
const PREFIX = "H3S1:";
const ZIP_PREFIX = "H3S1Z:";
const STYLE_ID = "h3studio-release-fixups-style";

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .h3s-share-section[data-h3s-share-v2="true"] .h3s-share-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
    .h3s-share-section[data-h3s-share-v2="true"] .h3s-share-button{border:1px solid var(--h3s-border,#35414a);background:var(--h3s-panel-2,#172127);color:inherit;border-radius:8px;padding:7px 8px;cursor:pointer;font:inherit;min-width:0}
    .h3s-share-section[data-h3s-share-v2="true"] .h3s-share-button:hover{border-color:var(--h3s-accent,#00cfa6)}
    .h3s-share-section[data-h3s-share-v2="true"] .h3s-share-button.primary{border-color:color-mix(in srgb,var(--h3s-accent,#00cfa6) 68%,var(--h3s-border,#35414a))}
    .h3s-share-section[data-h3s-share-v2="true"] .h3s-share-meta{font-size:10px;opacity:.65;line-height:1.4}
    @media(max-width:560px){.h3s-share-section[data-h3s-share-v2="true"] .h3s-share-actions{grid-template-columns:1fr}}
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

function sourceForInput(node, inputName) {
  const input = node?.inputs?.find((candidate) => candidate.name === inputName);
  const link = graphLink(input?.link);
  if (!link) return null;
  const id = link.origin_id ?? link.originId ?? link.source_id;
  return app.graph?.getNodeById?.(Number(id)) || null;
}

function inputComesFrom(node, inputName, sourceNode) {
  const input = node?.inputs?.find((candidate) => candidate.name === inputName);
  const link = graphLink(input?.link);
  if (!link) return false;
  const id = Number(link.origin_id ?? link.originId ?? link.source_id);
  return id === Number(sourceNode?.id);
}

function connectedLoader(director) {
  // Director itself does not have h3_bundle. Follow the shared downstream
  // Condition/Benchmark node and then walk its h3_bundle input back to Loader.
  for (const candidate of app.graph?._nodes || []) {
    if (!inputComesFrom(candidate, "studio_context", director)) continue;
    const loader = sourceForInput(candidate, "h3_bundle");
    if (loader?.comfyClass === LOADER) return loader;
  }
  const loaders = (app.graph?._nodes || []).filter((candidate) => candidate?.comfyClass === LOADER);
  return loaders.length === 1 ? loaders[0] : null;
}

function loaderAssets(director) {
  const loader = connectedLoader(director);
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
      mode: g.mode,
      route: g.route,
      aspect_ratio: g.aspect_ratio,
      megapixels: g.megapixels,
      custom_width: g.custom_width,
      custom_height: g.custom_height,
      sampling_profile: g.sampling_profile,
      frame_profile: g.frame_profile,
      cap_native_resolution: Boolean(g.cap_native_resolution),
    },
    p: {
      enhance_mode: p.enhance_mode,
      analyze_images: Boolean(p.analyze_images),
      deep_enhancement: Boolean(p.deep_enhancement),
      adherence: p.adherence,
      detail_level: p.detail_level,
      analyzer_resolution: p.analyzer_resolution,
    },
    r: {
      preset: String(ui.runtime_optimization || "auto"),
      advanced: ui.runtime_advanced || {},
    },
    l: Array.isArray(ui.custom_loras) ? ui.custom_loras.map((item) => ({
      name: String(item?.name || "").replaceAll("\\", "/"),
      strength: Number(item?.strength ?? 1),
      enabled: item?.enabled !== false,
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
  const normalized = String(value).replaceAll("-", "+").replaceAll("_", "/");
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
  if (typeof DecompressionStream !== "function") throw new Error("This browser cannot unpack compressed H3S presets.");
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

function extractCode(text) {
  const source = String(text || "");
  const matches = [ZIP_PREFIX, PREFIX]
    .map((prefix) => ({ prefix, index: source.indexOf(prefix) }))
    .filter((item) => item.index >= 0)
    .sort((a, b) => a.index - b.index);
  if (!matches.length) return "";
  return source.slice(matches[0].index).split(/\s/)[0];
}

async function decodePreset(raw) {
  const text = String(raw || "").trim();
  const code = extractCode(text);
  let value;
  if (code.startsWith(ZIP_PREFIX)) {
    const bytes = await gunzipBytes(base64UrlToBytes(code.slice(ZIP_PREFIX.length)));
    value = JSON.parse(new TextDecoder().decode(bytes));
  } else if (code.startsWith(PREFIX)) {
    value = JSON.parse(new TextDecoder().decode(base64UrlToBytes(code.slice(PREFIX.length))));
  } else {
    value = JSON.parse(text);
  }
  if (!value || Number(value.v || 0) !== 1) throw new Error("Unsupported H3 Studio preset version.");
  return value;
}

function widgetChoices(target) {
  let values = target?.options?.values;
  if (typeof values === "function") {
    try { values = values(); } catch { values = null; }
  }
  return Array.isArray(values) ? values.map(String) : null;
}

function setLoaderAssets(director, assets) {
  const loader = connectedLoader(director);
  if (!loader || !assets || typeof assets !== "object") return { loader: false, changed: 0, missing: [] };
  let changed = 0;
  const missing = [];
  for (const [name, rawValue] of Object.entries(assets)) {
    const value = String(rawValue || "");
    if (!value) continue;
    const target = widget(loader, name);
    if (!target || String(target.value) === value) continue;
    const choices = widgetChoices(target);
    if (choices && !choices.includes(value)) {
      missing.push(`${name}: ${value}`);
      continue;
    }
    target.value = value;
    target.callback?.(value, app.canvas, loader, [0, 0], {});
    changed += 1;
  }
  if (changed) {
    loader.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
  }
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
    custom_loras: Array.isArray(preset.l) ? preset.l.map((item) => ({
      name: String(item?.name || "").replaceAll("\\", "/"),
      strength: Number(item?.strength ?? 1),
      enabled: item?.enabled !== false,
    })).filter((item) => item.name) : [],
  };
  applyState(node, state);
  const result = setLoaderAssets(node, preset.a);

  // applyState persists the values, but the Director's large custom DOM is a
  // rendered view of that state. Force that view and the add-on sections to
  // rebuild immediately so import visibly changes every control.
  node.__h3studioConfigured?.();
  setTimeout(() => {
    node.__h3studioPanel?.querySelector(":scope > .h3s-runtime-section")?.remove();
    node.__h3studioPanel?.querySelector(":scope > .h3s-custom-loras")?.remove();
    try { node.onConfigure?.(node.serialize?.() || {}); } catch {}
    ensureShare(node, true);
  }, 0);
  return result;
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
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
  try { app.extensionManager?.toast?.add?.({ severity, summary, detail, life: 5000 }); }
  catch { console.log(`[H3 Studio] ${summary}: ${detail}`); }
}

function button(text, title, onClick, primary = false) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = `h3s-share-button${primary ? " primary" : ""}`;
  el.textContent = text;
  el.title = title;
  el.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    try { await onClick(); } catch (error) { toast("H3 Studio preset", String(error?.message || error), "error"); }
  });
  return el;
}

function summaryLine(node) {
  const state = stateFromNode(node);
  const ui = state.ui || {};
  const loras = (ui.custom_loras || []).filter((item) => item?.enabled !== false && item?.name).length;
  const model = loaderAssets(node);
  const transformer = state.generation.route === "ref2va" ? model.ref2va_model : model.fl2va_model;
  return `H3 Studio · ${String(ui.runtime_optimization || "auto").replaceAll("_", " ")} · ${state.generation.sampling_profile} · ${Number(state.generation.megapixels || 0).toFixed(2)} MP · ${loras} LoRA${loras === 1 ? "" : "s"}${transformer ? ` · ${transformer.split("/").pop()}` : ""}`;
}

function buildShare(node) {
  const section = document.createElement("section");
  section.className = "h3s-section h3s-share-section";
  section.dataset.h3sShareV2 = "true";
  const header = document.createElement("div");
  header.className = "h3s-section-header";
  const title = document.createElement("span"); title.className = "h3s-section-title"; title.textContent = "Share Preset";
  const pill = document.createElement("span"); pill.className = "h3s-status-pill"; pill.textContent = "H3S1";
  header.append(title, pill);
  const body = document.createElement("div"); body.className = "h3s-section-stack h3s-share-body";
  const help = document.createElement("p"); help.className = "h3s-context-help";
  help.textContent = "Copies the actual Director runtime/sampling/resolution/LoRA state plus the connected Loader model choices. Import applies them immediately; prompts and references stay private.";
  const actions = document.createElement("div"); actions.className = "h3s-share-actions";
  actions.append(
    button("Copy Discord", "Copy summary + compact preset", async () => {
      const code = await encodePreset(node);
      await copyText(`${summaryLine(node)}\n${code}`);
      toast("Preset copied", `${code.length} character ${code.startsWith(ZIP_PREFIX) ? "compressed " : ""}H3S preset`);
    }, true),
    button("Copy code", "Copy only the H3S code", async () => {
      const code = await encodePreset(node);
      await copyText(code);
      toast("Preset code copied", `${code.length} characters`);
    }),
    button("Paste / Import", "Paste H3S1/H3S1Z or JSON", async () => {
      const raw = globalThis.prompt?.("Paste H3S preset code or JSON:", "");
      if (!raw) return;
      const preset = await decodePreset(raw);
      const result = applyPreset(node, preset);
      const missing = result.missing || [];
      const detail = result.loader
        ? `Director + LoRAs + runtime restored · ${result.changed} Loader field${result.changed === 1 ? "" : "s"} changed${missing.length ? ` · ${missing.length} model asset${missing.length === 1 ? "" : "s"} missing locally` : ""}`
        : "Director restored. No unique connected Loader was found, so Loader model choices were not changed.";
      toast("Preset imported", detail, !result.loader || missing.length ? "warn" : "success");
      if (missing.length) console.warn("[H3 Studio] Shared preset assets missing locally:\n" + missing.join("\n"));
    }),
  );
  const meta = document.createElement("div"); meta.className = "h3s-share-meta";
  meta.textContent = "Portable: filenames and strengths only. No absolute paths, prompts, reference pixels or machine-specific Auto result are embedded.";
  body.append(help, actions, meta);
  section.append(header, body);
  return section;
}

function ensureShare(node, replace = false) {
  const panel = node?.__h3studioPanel;
  if (!panel?.isConnected) return false;
  const current = panel.querySelector(":scope > .h3s-share-section");
  if (current?.dataset?.h3sShareV2 === "true" && !replace) return true;
  const section = buildShare(node);
  if (current) current.replaceWith(section);
  else {
    const advanced = [...panel.children].find((child) => child.querySelector?.(".h3s-advanced-toggle"));
    panel.insertBefore(section, advanced || null);
  }
  return true;
}

function remountAddons(node) {
  if (node.__h3studioReleaseRemountQueued) return;
  node.__h3studioReleaseRemountQueued = true;
  queueMicrotask(() => {
    node.__h3studioReleaseRemountQueued = false;
    const panel = node.__h3studioPanel;
    if (!panel?.isConnected) return;
    ensureShare(node);
    const missingRuntime = !panel.querySelector(":scope > .h3s-runtime-section");
    if (missingRuntime && !node.__h3studioRuntimeRemounting) {
      node.__h3studioRuntimeRemounting = true;
      try { node.onConfigure?.(node.serialize?.() || {}); } catch {}
      setTimeout(() => { node.__h3studioRuntimeRemounting = false; ensureShare(node); }, 0);
    }
  });
}

function watchDirector(node) {
  if (!node || node.comfyClass !== DIRECTOR || node.__h3studioReleaseWatchStarted) return;
  node.__h3studioReleaseWatchStarted = true;
  let attempts = 0;
  const wait = () => {
    const panel = node.__h3studioPanel;
    if (!panel) {
      attempts += 1;
      if (attempts < 800) setTimeout(wait, 25);
      return;
    }
    installStyles();
    ensureShare(node, true);
    const observer = new MutationObserver(() => remountAddons(node));
    observer.observe(panel, { childList: true });
    node.__h3studioReleaseObserver = observer;
    remountAddons(node);
  };
  setTimeout(wait, 0);
}

app.registerExtension({
  name: "H3Studio.ReleaseFixups",
  afterConfigureGraph() {
    for (const node of app.graph?._nodes || []) if (node?.comfyClass === DIRECTOR) watchDirector(node);
  },
  nodeCreated(node) {
    if (node?.comfyClass === DIRECTOR) watchDirector(node);
  },
});
