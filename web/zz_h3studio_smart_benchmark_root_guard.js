import { app } from "../../scripts/app.js";

const TARGET = "H3StudioSmartBenchmark";
const WIDGET_NAME = "h3studio_smart_benchmark";
const STYLE_ID = "h3studio-smart-benchmark-container-v7";

function installResponsiveStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .h3b7{container-type:inline-size;min-width:0;box-sizing:border-box}
  `;
  document.head.append(style);
}

function isBenchmarkWidget(item) {
  return item?.name === WIDGET_NAME
    || item?.element?.dataset?.h3BenchmarkUi === "v7"
    || item?.element?.classList?.contains?.("h3b7");
}

function benchmarkWidgets(node) {
  return (node?.widgets || []).filter(isBenchmarkWidget);
}

function boundRoot(root, node) {
  if (!root) return;
  installResponsiveStyles();
  root.dataset.h3BenchmarkUi = "v7";
  root.dataset.h3BenchmarkNode = String(node.id ?? "");

  // ComfyUI owns the overlay's exact pixel width and canvas transform. The
  // benchmark renderer only manages its internal layout and vertical scroll.
  if (root.style.getPropertyPriority("width") === "important" && root.style.getPropertyValue("width") === "100%") root.style.removeProperty("width");
  if (root.style.getPropertyPriority("max-width") === "important" && root.style.getPropertyValue("max-width") === "100%") root.style.removeProperty("max-width");
  root.style.setProperty("min-width", "0", "important");
  root.style.setProperty("box-sizing", "border-box", "important");
  root.style.setProperty("max-height", "560px", "important");
  root.style.setProperty("overflow-y", "auto", "important");
  root.style.setProperty("overflow-x", "hidden", "important");
  root.style.setProperty("overscroll-behavior", "contain", "important");
  root.style.setProperty("contain", "layout paint", "important");
}

function dedupe(node, preferred = null) {
  const matches = benchmarkWidgets(node);
  if (!matches.length) return null;
  const keep = matches.find((item) => preferred && item.element === preferred)
    || matches.find((item) => item.element?.isConnected)
    || matches[0];
  if (keep.element) boundRoot(keep.element, node);

  for (const extra of matches) {
    if (extra === keep) continue;
    extra.element?.remove?.();
    extra.inputEl?.remove?.();
    const index = node.widgets.indexOf(extra);
    if (index >= 0) node.widgets.splice(index, 1);
  }
  if (matches.length > 1) console.warn(`[H3 Studio] Smart Benchmark root guard removed ${matches.length - 1} duplicate DOM widget(s).`);
  return keep;
}

function install(node) {
  if (!node || node.comfyClass !== TARGET) return;
  installResponsiveStyles();
  const root = node.__h3bRoot || dedupe(node)?.element || null;
  if (root) boundRoot(root, node);
  dedupe(node, root);

  if (node.__h3bRootGuardInstalled) return;
  node.__h3bRootGuardInstalled = true;

  const originalAdd = typeof node.addDOMWidget === "function" ? node.addDOMWidget.bind(node) : null;
  if (!originalAdd) return;
  node.addDOMWidget = function guardedAddDOMWidget(name, type, element, options = {}) {
    if (name === WIDGET_NAME) {
      const existing = dedupe(node, node.__h3bRoot);
      if (existing) return existing;
    }
    const created = originalAdd(name, type, element, options);
    if (name === WIDGET_NAME) {
      created.hideOnZoom = true;
      created.options ||= {};
      created.options.hideOnZoom = true;
      created.getMinHeight = () => 330;
      created.getMaxHeight = () => 560;
      if (element) boundRoot(element, node);
      queueMicrotask(() => dedupe(node, element));
    }
    return created;
  };
}

app.registerExtension({
  name: "H3Studio.SmartBenchmarkStableRootGuardV7",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== TARGET) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function h3BenchmarkRootGuardV7Created() {
      const result = created?.apply(this, arguments);
      install(this);
      return result;
    };
    const configured = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function h3BenchmarkRootGuardV7Configured() {
      const result = configured?.apply(this, arguments);
      install(this);
      queueMicrotask(() => dedupe(this, this.__h3bRoot));
      return result;
    };
  },
  nodeCreated(node) { if (node?.comfyClass === TARGET) install(node); },
  afterConfigureGraph() {
    setTimeout(() => {
      for (const node of app.graph?._nodes || []) if (node?.comfyClass === TARGET) install(node);
    }, 120);
  },
});
