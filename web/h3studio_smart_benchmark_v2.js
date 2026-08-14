import { app } from "../../scripts/app.js";

const SMART = "H3StudioSmartBenchmark";
const LEGACY = "H3StudioABComparison";
const STYLE_ID = "h3studio-smart-benchmark-v2-style";

function widget(node, name) {
  return node?.widgets?.find((candidate) => candidate.name === name) || null;
}

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .h3b-root{min-width:0!important;width:100%!important;max-width:100%!important;overflow:hidden!important;box-sizing:border-box!important;padding:12px!important;border:1px solid #2a3a42!important;border-radius:12px!important;background:radial-gradient(circle at 90% 0,rgba(45,212,191,.07),transparent 27%),linear-gradient(180deg,#0e171b,#0a1115)!important;box-shadow:0 10px 30px rgba(0,0,0,.18)!important}
    .h3b-root *{box-sizing:border-box;min-width:0}
    .h3b-head{align-items:center!important;margin-bottom:10px!important;padding-bottom:9px;border-bottom:1px solid #223039}
    .h3b-head strong{font-size:14px!important;letter-spacing:.01em}.h3b-help{max-width:620px!important;color:#8fa2ab!important}
    .h3b-status{padding:4px 7px;border:1px solid #27453f;border-radius:999px;background:#10231f;white-space:nowrap;color:#78dfc7!important}
    .h3b-toolbar,.h3b-share{display:grid!important;grid-template-columns:repeat(auto-fit,minmax(118px,1fr))!important;gap:6px!important;margin-bottom:7px!important}
    .h3b-button{width:100%!important;min-height:30px!important;padding:6px 8px!important;border-radius:7px!important;background:#121d22!important;border-color:#30414a!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .h3b-button.primary{background:#123128!important;border-color:#1e846e!important;color:#d7fff6!important}
    .h3b-summary{margin:9px 0 10px!important;padding:8px 10px!important;border-radius:8px!important;background:#0e1a1f!important;border-color:#263840!important;color:#a9bbc3!important}
    .h3b-v2-settings{display:grid;grid-template-columns:minmax(0,1fr) 140px 140px;gap:7px;align-items:end;margin:8px 0 10px;padding:8px;border:1px solid #25353d;border-radius:9px;background:#0c1519}
    .h3b-v2-note{font-size:10px;color:#80939c;line-height:1.4;padding:3px 2px 4px}
    .h3b-v2-setting label{display:block;font-size:9px;color:#748892;margin:0 0 3px 1px}.h3b-v2-setting input,.h3b-v2-setting select{width:100%;height:28px;border:1px solid #30414a;border-radius:6px;background:#091115;color:#dce8ed;padding:4px 6px}
    .h3b-scenarios{gap:9px!important}.h3b-card{overflow:hidden!important;border:1px solid #2a3a42!important;border-radius:10px!important;background:linear-gradient(180deg,#10191e,#0d1519)!important;padding:10px!important}
    .h3b-card-head{margin-bottom:9px!important}.h3b-card-index{background:#15382f!important;color:#8ff0d7!important}.h3b-card-name{height:30px!important;border:1px solid #30414a!important;border-radius:6px!important;background:#0a1216!important;color:#edf6f8!important;padding:5px 7px!important}
    .h3b-grid{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:7px!important}.h3b-grid>.h3b-field:first-child{grid-column:1/-1}
    .h3b-field label{color:#81949d!important}.h3b-field input,.h3b-field select{max-width:100%!important;width:100%!important;height:30px!important;padding:5px 7px!important;background:#091115!important;border-color:#30414a!important}
    .h3b-loras{margin-top:9px!important;padding-top:8px!important}.h3b-lora-picker{grid-template-columns:minmax(0,1fr) 104px!important}.h3b-lora-picker input{max-width:100%!important;height:30px!important;background:#091115!important;border-color:#30414a!important}
    .h3b-lora-row{grid-template-columns:22px minmax(0,1fr) 78px 26px!important;padding:6px 7px!important;background:#0a1317!important}.h3b-lora-strength{max-width:78px!important}
    .h3b-warning{padding:6px 8px;border-radius:6px;background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.14)}
    .h3b-empty{background:#0a1317!important}.h3b-root datalist{max-width:100%}
    @media(max-width:760px){.h3b-grid{grid-template-columns:1fr 1fr!important}.h3b-grid>.h3b-field:first-child{grid-column:1/-1}.h3b-v2-settings{grid-template-columns:1fr 1fr}.h3b-v2-note{grid-column:1/-1}.h3b-toolbar,.h3b-share{grid-template-columns:1fr 1fr!important}}
  `;
  document.head.append(style);
}

function hideNativeWidget(node, name) {
  const target = widget(node, name);
  if (!target || target.__h3bV2Hidden) return;
  target.__h3bV2Hidden = true;
  target.__h3bV2ComputeSize = target.computeSize;
  target.computeSize = () => [0, -4];
  target.hidden = true;
  target.type = "h3studio_hidden";
}

function setWidget(node, name, value) {
  const target = widget(node, name);
  if (!target) return;
  target.value = value;
  target.callback?.(value, app.canvas, node, [0, 0], {});
  node.setDirtyCanvas?.(true, true);
}

function settings(node, root) {
  let box = root.querySelector(":scope > .h3b-v2-settings");
  if (box) return box;
  box = document.createElement("div");
  box.className = "h3b-v2-settings";
  const note = document.createElement("div");
  note.className = "h3b-v2-note";
  note.textContent = "Build clean same-seed scenarios here. Only the fields you change differ; model, runtime, Sampling Profile, LoRAs and strengths are preserved exactly.";

  const makeNumber = (label, name, min, max, step) => {
    const wrap = document.createElement("div"); wrap.className = "h3b-v2-setting";
    const title = document.createElement("label"); title.textContent = label;
    const input = document.createElement("input"); input.type = "number"; input.min = String(min); input.max = String(max); input.step = String(step); input.value = String(widget(node, name)?.value ?? min);
    input.addEventListener("change", () => setWidget(node, name, Math.max(min, Math.min(max, Number(input.value) || min))));
    wrap.append(title, input); return wrap;
  };
  box.append(note, makeNumber("Scenario guard", "max_scenarios", 1, 24, 1), makeNumber("Result grid size", "grid_cell_size", 320, 896, 64));
  const summary = root.querySelector(":scope > .h3b-summary");
  root.insertBefore(box, summary || root.querySelector(":scope > .h3b-scenarios") || null);
  return box;
}

function polish(node) {
  if (!node || node.comfyClass !== SMART) return;
  installStyles();
  hideNativeWidget(node, "scenarios_json");
  hideNativeWidget(node, "max_scenarios");
  hideNativeWidget(node, "grid_cell_size");
  const root = node.__h3bRoot;
  if (!root?.isConnected) return;
  root.dataset.h3bV2 = "true";
  settings(node, root);
  const parent = root.parentElement;
  if (parent) {
    parent.style.background = "transparent";
    parent.style.border = "0";
    parent.style.padding = "0";
    parent.style.margin = "0";
    parent.style.overflow = "hidden";
    parent.style.maxWidth = "100%";
    parent.style.width = "100%";
  }
  const size = node.size || [0, 0];
  if (Number(size[0]) < 720) node.setSize?.([720, Math.max(560, Number(size[1]) || 560)]);
}

function watchSmart(node) {
  if (!node || node.comfyClass !== SMART || node.__h3bV2Watch) return;
  node.__h3bV2Watch = true;
  let attempts = 0;
  const wait = () => {
    if (!node.__h3bRoot?.isConnected) {
      attempts += 1;
      if (attempts < 600) setTimeout(wait, 25);
      return;
    }
    polish(node);
    const parent = node.__h3bRoot.parentElement;
    if (!parent) return;
    const observer = new MutationObserver(() => queueMicrotask(() => polish(node)));
    observer.observe(parent, { childList: true, subtree: false });
    node.__h3bV2Observer = observer;
  };
  setTimeout(wait, 0);
}

function graphLink(id) {
  const links = app.graph?.links;
  if (!links || id == null) return null;
  return typeof links.get === "function" ? links.get(id) : links[id];
}

function inputSource(oldNode, inputName) {
  const input = oldNode?.inputs?.find((candidate) => candidate.name === inputName);
  const link = graphLink(input?.link);
  if (!link) return null;
  return {
    node: app.graph?.getNodeById?.(Number(link.origin_id ?? link.originId ?? link.source_id)),
    slot: Number(link.origin_slot ?? link.originSlot ?? link.source_slot ?? 0),
  };
}

function outputTargets(oldNode, outputIndex) {
  const ids = oldNode?.outputs?.[outputIndex]?.links || [];
  return ids.map((id) => graphLink(id)).filter(Boolean).map((link) => ({
    node: app.graph?.getNodeById?.(Number(link.target_id ?? link.targetId)),
    slot: Number(link.target_slot ?? link.targetSlot ?? 0),
  })).filter((item) => item.node);
}

function inputIndex(node, name) {
  return Math.max(0, (node.inputs || []).findIndex((candidate) => candidate.name === name));
}

function migrateLegacyNode(oldNode) {
  const factory = globalThis.LiteGraph?.createNode;
  if (typeof factory !== "function") {
    console.warn("[H3 Studio] Legacy Benchmark Lab detected, but LiteGraph.createNode is unavailable; add Smart Benchmark Lab manually.");
    return null;
  }
  const bundle = inputSource(oldNode, "h3_bundle");
  const context = inputSource(oldNode, "studio_context");
  const imageTargets = outputTargets(oldNode, 0);
  const reportTargets = outputTargets(oldNode, 1);
  const oldGrid = Number(widget(oldNode, "grid_cell_size")?.value || 576);
  const node = factory.call(globalThis.LiteGraph, SMART);
  if (!node) return null;
  node.pos = Array.isArray(oldNode.pos) ? [...oldNode.pos] : oldNode.pos;
  node.size = [720, Math.max(560, Number(oldNode.size?.[1]) || 560)];
  node.title = "H3 Studio · Smart Benchmark Lab";
  node.properties ||= {};
  node.properties.h3studio_migrated_from_legacy_benchmark = true;
  app.graph.add(node);
  app.graph.remove(oldNode);
  if (bundle?.node) bundle.node.connect?.(bundle.slot, node, inputIndex(node, "h3_bundle"));
  if (context?.node) context.node.connect?.(context.slot, node, inputIndex(node, "studio_context"));
  for (const target of imageTargets) node.connect?.(0, target.node, target.slot);
  for (const target of reportTargets) node.connect?.(1, target.node, target.slot);
  setWidget(node, "scenarios_json", "[]");
  setWidget(node, "max_scenarios", 12);
  setWidget(node, "grid_cell_size", Math.max(320, Math.min(896, oldGrid || 576)));
  console.info("[H3 Studio] Migrated legacy Benchmark Lab to Smart Benchmark Lab.");
  return node;
}

function migrateLegacyBenchmarks() {
  const legacy = [...(app.graph?._nodes || [])].filter((node) => node?.comfyClass === LEGACY);
  if (!legacy.length) return;
  for (const node of legacy) {
    const migrated = migrateLegacyNode(node);
    if (migrated) watchSmart(migrated);
  }
  app.graph?.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "H3Studio.SmartBenchmarkV2",
  afterConfigureGraph() {
    setTimeout(() => {
      migrateLegacyBenchmarks();
      for (const node of app.graph?._nodes || []) if (node?.comfyClass === SMART) watchSmart(node);
    }, 80);
  },
  nodeCreated(node) {
    if (node?.comfyClass === SMART) watchSmart(node);
  },
});
