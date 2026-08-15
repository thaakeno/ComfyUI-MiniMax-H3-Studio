import { app } from "../../scripts/app.js";

const DIRECTOR = "H3StudioDirector";
const STYLE_ID = "h3studio-native-tool-ui-v7";
const VISIBLE_NATIVE = new Set(["prompt", "h3_prompt_mentions", "h3studio_controls"]);
const MAX_HEIGHT = 980;

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .h3s-studio-panel.h3s-native-v7{
      --h3s-bg:#2a2d32!important;
      --h3s-panel:#30343a!important;
      --h3s-panel-2:#363b42!important;
      --h3s-panel-3:#3b4048!important;
      --h3s-border:#474c55!important;
      --h3s-border-soft:#3b4047!important;
      --h3s-text:#f3f4f6!important;
      --h3s-muted:#aeb4bd!important;
      --h3s-muted-2:#858c96!important;
      --h3s-accent:#91a7c7!important;
      --h3s-accent-soft:#3a4657!important;
      --h3s-danger:#d98f96!important;
      width:100%!important;
      max-width:100%!important;
      max-height:640px!important;
      overflow:auto!important;
      overscroll-behavior:contain!important;
      scrollbar-gutter:stable!important;
      background:var(--h3s-bg)!important;
      border:1px solid var(--h3s-border)!important;
      border-radius:10px!important;
      color:var(--h3s-text)!important;
      box-shadow:0 8px 22px rgba(0,0,0,.16)!important;
      font:12px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important;
      contain:layout paint!important;
    }
    .h3s-native-v7 *{box-sizing:border-box;min-width:0}
    .h3s-native-v7::-webkit-scrollbar{width:9px}.h3s-native-v7::-webkit-scrollbar-thumb{background:#555b64;border:2px solid #2a2d32;border-radius:999px}
    .h3s-native-v7 .h3s-studio-header{
      position:sticky!important;top:0!important;z-index:12!important;
      min-height:44px!important;padding:0 14px!important;
      background:#30343a!important;border-bottom:1px solid var(--h3s-border-soft)!important;
      box-shadow:none!important;
    }
    .h3s-native-v7 .h3s-studio-brand{gap:8px!important}.h3s-native-v7 .h3s-studio-mark{width:18px!important;height:18px!important;border-radius:5px!important;background:#41464e!important;box-shadow:none!important}
    .h3s-native-v7 .h3s-studio-mark::after{content:'H3';display:grid;place-items:center;width:100%;height:100%;font:800 7px/1 system-ui;color:#f4f5f7}
    .h3s-native-v7 .h3s-studio-title{font-size:12px!important;font-weight:720!important;letter-spacing:0!important}.h3s-native-v7 .h3s-status-pill{padding:3px 6px!important;border:0!important;border-radius:5px!important;background:#41464e!important;color:#d5d9de!important;font-size:8px!important;letter-spacing:0!important}

    .h3s-v7-shell{display:grid;grid-template-columns:minmax(0,1fr) 270px;align-items:start;background:#2a2d32}
    .h3s-v7-primary{min-width:0;padding:0 16px 14px 16px;border-right:1px solid var(--h3s-border-soft);background:#2d3035}
    .h3s-v7-inspector{min-width:0;background:#292c31}
    .h3s-v7-primary>.h3s-section,.h3s-v7-primary>.h3s-result{margin:0!important;border:0!important;border-bottom:1px solid var(--h3s-border-soft)!important;border-radius:0!important;background:transparent!important;box-shadow:none!important}
    .h3s-v7-primary>.h3s-section:last-child,.h3s-v7-primary>.h3s-result:last-child{border-bottom:0!important}
    .h3s-v7-primary>.h3s-section{padding:15px 0!important}.h3s-v7-inspector>.h3s-section{margin:0!important;padding:12px 12px!important;border:0!important;border-bottom:1px solid var(--h3s-border-soft)!important;border-radius:0!important;background:transparent!important;box-shadow:none!important}
    .h3s-v7-inspector>.h3s-section:last-child{border-bottom:0!important}
    .h3s-v7-primary .h3s-section-header,.h3s-v7-inspector .h3s-section-header{min-height:22px!important;margin:0 0 8px!important}.h3s-v7-primary .h3s-section-title,.h3s-v7-inspector .h3s-section-title{font-size:11px!important;font-weight:720!important;letter-spacing:0!important;text-transform:none!important;color:#e4e7eb!important}
    .h3s-v7-primary .h3s-section-description,.h3s-v7-inspector .h3s-section-description{margin:-3px 0 9px!important;color:var(--h3s-muted-2)!important;font-size:9.5px!important;line-height:1.4!important}
    .h3s-v7-primary .h3s-context-help,.h3s-v7-inspector .h3s-context-help{margin:3px 0!important;color:#949ba5!important;font-size:9px!important;line-height:1.45!important}

    .h3s-native-v7 .h3s-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:9px!important}.h3s-v7-inspector .h3s-grid{grid-template-columns:1fr!important;gap:8px!important}
    .h3s-native-v7 .h3s-field{gap:4px!important}.h3s-native-v7 .h3s-field-label{margin:0!important;color:#aeb4bd!important;font-size:9px!important;font-weight:650!important;text-transform:none!important;letter-spacing:0!important}.h3s-native-v7 .h3s-field-hint{font-size:8.5px!important;color:#828995!important}
    .h3s-native-v7 .h3s-control,.h3s-native-v7 .h3s-number,.h3s-native-v7 .h3s-writer-instruction,.h3s-native-v7 .h3s-reference-description,.h3s-native-v7 input,.h3s-native-v7 textarea{
      border:1px solid #4b5059!important;border-radius:6px!important;background:#363a40!important;color:#f2f3f5!important;box-shadow:none!important;
    }
    .h3s-native-v7 .h3s-control{height:31px!important;padding:5px 8px!important}.h3s-native-v7 input:focus,.h3s-native-v7 textarea:focus,.h3s-native-v7 .h3s-control:focus{outline:none!important;border-color:#71829a!important;box-shadow:0 0 0 2px rgba(145,167,199,.10)!important}
    .h3s-native-v7 .h3s-choice-trigger{height:31px!important;padding:5px 8px!important;border:1px solid #4b5059!important;border-radius:6px!important;background:#363a40!important;color:#f1f3f5!important;box-shadow:none!important}.h3s-native-v7 .h3s-choice-trigger:hover{background:#3b4047!important;border-color:#5b616b!important}.h3s-native-v7 .h3s-choice-value{font-size:9.5px!important}
    .h3s-choice-menu{background:#33373d!important;border-color:#515762!important;border-radius:7px!important;box-shadow:0 12px 30px rgba(0,0,0,.28)!important}.h3s-choice-option{border-radius:5px!important}.h3s-choice-option:hover,.h3s-choice-option:focus{background:#424750!important}.h3s-choice-option.is-active{background:#465267!important}

    .h3s-v7-primary .h3s-final-result{margin-top:4px!important;border:1px solid #464b53!important;border-radius:8px!important;background:#24272b!important;overflow:hidden!important}.h3s-v7-primary .h3s-output-stage{display:grid!important;place-items:center!important;min-height:250px!important;max-height:430px!important;padding:8px!important;background:#202226!important}.h3s-v7-primary .h3s-final-image{display:block!important;width:100%!important;height:auto!important;max-height:410px!important;object-fit:contain!important;border-radius:5px!important}.h3s-v7-primary .h3s-output-tabs{padding:7px!important;background:#30343a!important;border-bottom:1px solid #41464d!important}.h3s-v7-primary .h3s-output-tab,.h3s-v7-primary .h3s-final-action,.h3s-v7-primary .h3s-copy-result{border:1px solid #4b5058!important;border-radius:5px!important;background:#393d43!important;color:#dfe2e6!important;box-shadow:none!important}.h3s-v7-primary .h3s-output-tab.is-active{background:#4a5361!important;border-color:#657389!important;color:#fff!important}.h3s-v7-primary .h3s-final-metadata{padding:7px 9px!important;color:#9da4ad!important;font-size:9px!important}.h3s-v7-primary .h3s-final-actions{padding:0 8px 8px!important}

    .h3s-native-v7 .h3s-reference-list{gap:7px!important}.h3s-native-v7 .h3s-reference-card{display:grid!important;grid-template-columns:88px minmax(0,1fr)!important;gap:10px!important;padding:8px 0!important;border:0!important;border-top:1px solid #3f444b!important;border-radius:0!important;background:transparent!important;box-shadow:none!important}.h3s-native-v7 .h3s-reference-card:first-child{border-top:0!important}.h3s-native-v7 .h3s-reference-thumb{min-height:72px!important;border:1px solid #454a52!important;border-radius:6px!important;background:#202327!important;overflow:hidden!important}.h3s-native-v7 .h3s-reference-controls{grid-template-columns:1fr 1fr!important;gap:6px!important}.h3s-native-v7 .h3s-reference-description{min-height:54px!important;padding:7px!important;font-size:9px!important;line-height:1.4!important}.h3s-native-v7 .h3s-reference-help{font-size:8.5px!important;color:#858c96!important}.h3s-native-v7 .h3s-auto-role{display:inline-block!important;width:max-content!important;max-width:100%!important;padding:2px 5px!important;border:0!important;border-radius:4px!important;background:#3a4048!important;color:#b7bec7!important;font-size:8px!important}.h3s-native-v7 .h3s-icon-button{width:24px!important;height:24px!important;border:0!important;border-radius:5px!important;background:transparent!important;color:#9ea5af!important}.h3s-native-v7 .h3s-icon-button:hover{background:#41464e!important;color:#fff!important}

    .h3s-v7-inspector .h3s-resolution-presets{display:flex!important;gap:4px!important;flex-wrap:wrap!important}.h3s-v7-inspector .h3s-resolution-preset,.h3s-v7-inspector .h3s-resolution-mode{min-height:25px!important;padding:4px 7px!important;border:1px solid #484e56!important;border-radius:5px!important;background:#35393f!important;color:#aeb4bd!important;font-size:8px!important}.h3s-v7-inspector .h3s-resolution-preset.is-active,.h3s-v7-inspector .h3s-resolution-mode.is-active{background:#4a5462!important;border-color:#68768b!important;color:#fff!important}.h3s-v7-inspector .h3s-resolution-preview{padding:7px!important;border:0!important;border-radius:6px!important;background:#34383e!important}.h3s-v7-inspector .h3s-resolution-result strong{font-size:10px!important}.h3s-v7-inspector .h3s-resolution-result span,.h3s-v7-inspector .h3s-resolution-note{font-size:8px!important}

    .h3s-v7-inspector .h3rt{gap:7px!important}.h3s-v7-inspector .h3rt-copy{display:grid!important;grid-template-columns:1fr auto!important;gap:6px!important}.h3s-v7-inspector .h3rt-copy p{font-size:8.5px!important;line-height:1.35!important}.h3s-v7-inspector .h3rt-presets{display:flex!important;flex-wrap:wrap!important;gap:4px!important}.h3s-v7-inspector .h3rt-more{display:contents!important}.h3s-v7-inspector .h3rt-preset{flex:1 1 76px!important;min-height:31px!important;padding:5px 7px!important;border:1px solid #484e56!important;border-radius:5px!important;background:#35393f!important;transform:none!important;box-shadow:none!important}.h3s-v7-inspector .h3rt-preset:hover{transform:none!important;background:#3d4249!important}.h3s-v7-inspector .h3rt-preset.is-active{background:#4a5462!important;border-color:#68768b!important}.h3s-v7-inspector .h3rt-preset-name{font-size:9px!important}.h3s-v7-inspector .h3rt-preset-sub{display:none!important}.h3s-v7-inspector .h3rt-status{grid-template-columns:1fr!important;gap:4px!important}.h3s-v7-inspector .h3rt-chip{padding:5px 6px!important;border:0!important;border-radius:5px!important;background:#34383e!important}.h3s-v7-inspector .h3rt-chip b{font-size:7.5px!important}.h3s-v7-inspector .h3rt-chip span{font-size:8.5px!important}.h3s-v7-inspector .h3rt-result{padding:7px!important;border:0!important;border-radius:6px!important;background:#343b46!important}.h3s-v7-inspector .h3rt-result-grid{grid-template-columns:1fr 1fr!important}.h3s-v7-inspector .h3rt-detect{padding:5px 7px!important;border-radius:5px!important;background:#373b41!important}

    .h3s-native-v7 .h3s-share-section .h3s-status-pill{display:none!important}.h3s-native-v7 .h3s-share-actions{grid-template-columns:1fr 1fr!important;gap:5px!important}.h3s-native-v7 .h3s-share-button{padding:6px 7px!important;border:1px solid #484e56!important;border-radius:5px!important;background:#35393f!important;color:#e2e5e8!important}.h3s-native-v7 .h3s-share-meta{font-size:8px!important;color:#858c96!important}.h3s-native-v7 .h3s-share-body>.h3s-context-help{display:none!important}
    .h3s-native-v7 .h3s-lora-stack{gap:5px!important}.h3s-native-v7 .h3s-lora-warning{padding:6px!important;border-radius:5px!important;background:#413a32!important;color:#d7bea0!important;font-size:8.5px!important}.h3s-native-v7 .h3s-lora-empty{padding:6px!important;border:0!important;background:#34383e!important;border-radius:5px!important;font-size:8.5px!important}

    .h3s-native-v7 .h3s-result{margin:0!important;padding:10px 0!important;background:transparent!important}.h3s-native-v7 .h3s-result>summary{padding:0!important}.h3s-native-v7 .h3s-result-prompt{margin-top:7px!important;background:#24272b!important;border:1px solid #40454d!important;border-radius:6px!important;max-height:180px!important;overflow:auto!important}
    .h3s-native-v7 .h3s-advanced-toggle{width:100%!important;padding:6px 0!important;border:0!important;background:transparent!important;color:#aeb4bd!important}

    @media(max-width:760px){.h3s-v7-shell{grid-template-columns:1fr}.h3s-v7-primary{border-right:0;border-bottom:1px solid var(--h3s-border-soft)}.h3s-v7-inspector .h3s-grid{grid-template-columns:1fr 1fr!important}}
    @media(max-width:560px){.h3s-native-v7 .h3s-grid,.h3s-v7-inspector .h3s-grid,.h3s-native-v7 .h3s-reference-controls{grid-template-columns:1fr!important}.h3s-native-v7 .h3s-reference-card{grid-template-columns:74px minmax(0,1fr)!important}}
  `;
  document.head.append(style);
}

function sectionTitle(element) {
  return String(element?.querySelector?.(".h3s-section-title")?.textContent || "").trim();
}

function forceHideNativeWidgets(node) {
  if (!node || node.comfyClass !== DIRECTOR) return;
  for (const item of node.widgets || []) {
    if (!item?.name || VISIBLE_NATIVE.has(item.name)) continue;
    item.hidden = true;
    item.type = "hidden";
    item.computeSize = () => [0, 0];
    if (item.inputEl?.style) item.inputEl.style.display = "none";
    if (item.element?.style && item.name !== "h3studio_controls") item.element.style.display = "none";
  }
}

function normalizeCopyLabels(root) {
  const share = root.querySelector(".h3s-share-section");
  if (!share) return;
  const title = share.querySelector(".h3s-section-title");
  if (title) title.textContent = "Preset";
  const buttons = [...share.querySelectorAll("button")];
  for (const button of buttons) {
    const text = String(button.textContent || "").trim();
    if (text === "Copy Discord") {
      button.textContent = "Copy preset";
      button.title = "Copy a readable preset summary and portable H3S code";
    } else if (text === "Paste / Import") {
      button.textContent = "Import";
    } else if (text === "Copy effective run config") {
      button.textContent = "Copy run config";
    }
  }
}

function decoratePanel(node) {
  const root = node?.__h3studioPanel;
  if (!root?.isConnected || root.__h3sDecorating) return;
  root.__h3sDecorating = true;
  const observer = root.__h3sV7Observer;
  observer?.disconnect?.();
  try {
    installStyles();
    forceHideNativeWidgets(node);
    node.color = "#3a3e45";
    node.bgcolor = "#272a2f";
    if (Array.isArray(node.size) && Number(node.size[1]) > MAX_HEIGHT) node.size[1] = MAX_HEIGHT;

    root.classList.add("h3s-native-v7");
    normalizeCopyLabels(root);

    let shell = root.querySelector(":scope > .h3s-v7-shell");
    if (!shell) {
      shell = document.createElement("div");
      shell.className = "h3s-v7-shell";
      const primary = document.createElement("main");
      primary.className = "h3s-v7-primary";
      const inspector = document.createElement("aside");
      inspector.className = "h3s-v7-inspector";
      shell.append(primary, inspector);
      root.append(shell);
    }
    const primary = shell.querySelector(":scope > .h3s-v7-primary");
    const inspector = shell.querySelector(":scope > .h3s-v7-inspector");

    const candidates = [...root.children].filter((child) =>
      child !== shell && !child.classList.contains("h3s-studio-header") && !child.classList.contains("h3s-state-warning")
    );
    for (const child of candidates) {
      const title = sectionTitle(child);
      if (
        title === "Generation" || title === "Runtime" || title === "Custom LoRAs" || title === "Share Preset" || title === "Preset"
        || child.querySelector?.(".h3s-advanced-toggle")
      ) inspector.append(child);
      else primary.append(child);
    }

    const primaryOrder = ["Direction", "Generated output", "References"];
    const primaryChildren = [...primary.children];
    primaryChildren.sort((a, b) => {
      const ai = primaryOrder.indexOf(sectionTitle(a));
      const bi = primaryOrder.indexOf(sectionTitle(b));
      const av = ai < 0 ? 99 : ai;
      const bv = bi < 0 ? 99 : bi;
      return av - bv;
    });
    for (const child of primaryChildren) primary.append(child);

    const inspectorOrder = ["Generation", "Runtime", "Custom LoRAs", "Preset"];
    const inspectorChildren = [...inspector.children];
    inspectorChildren.sort((a, b) => {
      const ai = inspectorOrder.indexOf(sectionTitle(a));
      const bi = inspectorOrder.indexOf(sectionTitle(b));
      const av = ai < 0 ? 99 : ai;
      const bv = bi < 0 ? 99 : bi;
      return av - bv;
    });
    for (const child of inspectorChildren) inspector.append(child);

    const widget = (node.widgets || []).find((item) => item?.name === "h3studio_controls");
    if (widget) {
      widget.options ||= {};
      widget.options.hideOnZoom = true;
      widget.hideOnZoom = true;
      widget.computedHeight = 640;
    }
  } finally {
    root.__h3sDecorating = false;
    observer?.observe?.(root, { childList: true });
  }
}

function scheduleDecorate(node) {
  if (node.__h3sV7Queued) return;
  node.__h3sV7Queued = true;
  requestAnimationFrame(() => {
    node.__h3sV7Queued = false;
    decoratePanel(node);
  });
}

function attach(node) {
  if (!node || node.comfyClass !== DIRECTOR) return;
  installStyles();
  forceHideNativeWidgets(node);
  const wait = () => {
    const root = node.__h3studioPanel;
    if (!root?.isConnected) {
      if (node.graph) setTimeout(wait, 40);
      return;
    }
    if (!root.__h3sV7Observer) {
      const observer = new MutationObserver(() => scheduleDecorate(node));
      root.__h3sV7Observer = observer;
      observer.observe(root, { childList: true });
    }
    decoratePanel(node);
  };
  setTimeout(wait, 0);

  if (!node.__h3sV7DrawWrapped) {
    node.__h3sV7DrawWrapped = true;
    const original = node.onDrawForeground;
    let last = 0;
    node.onDrawForeground = function h3sV7Draw() {
      const now = performance.now();
      if (now - last < 140) return;
      last = now;
      return original?.apply(this, arguments);
    };
  }
}

app.registerExtension({
  name: "H3Studio.NativeToolUIV7",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== DIRECTOR) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function h3sV7Created() {
      const result = created?.apply(this, arguments);
      attach(this);
      return result;
    };
    const configured = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function h3sV7Configured() {
      const result = configured?.apply(this, arguments);
      attach(this);
      scheduleDecorate(this);
      return result;
    };
  },
  setup() { installStyles(); },
  nodeCreated(node) { if (node?.comfyClass === DIRECTOR) attach(node); },
  afterConfigureGraph() {
    setTimeout(() => {
      for (const node of app.graph?._nodes || []) if (node?.comfyClass === DIRECTOR) attach(node);
    }, 80);
  },
});
