import { app } from "../../scripts/app.js";

const DIRECTOR = "H3StudioDirector";
const BENCHMARK = "H3StudioSmartBenchmark";
const STYLE_ID = "h3studio-product-ui-v5-style";
const VISIBLE_NATIVE = new Set(["prompt", "h3_prompt_mentions", "h3studio_controls"]);
const DRAW_INTERVAL_MS = 180;

const ICONS = Object.freeze({
  Generation: "◫",
  Direction: "✦",
  References: "▣",
  Runtime: "⚙",
  "Generated output": "↗",
  "Advanced controls": "⋯",
});

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    /* Product UI v5 — neutral, dense where useful, quiet everywhere else. */
    .h3s-studio-panel{
      --h3s-bg:#151719!important;
      --h3s-surface:#1b1e21!important;
      --h3s-raised:#22262a!important;
      --h3s-text:#f1f3f4!important;
      --h3s-muted:#9aa0a6!important;
      --h3s-border:#2b2f33!important;
      --h3s-accent:#8ab4f8!important;
      --h3s-warning:#e7b96f!important;
      width:100%!important;height:100%!important;gap:0!important;padding:0!important;
      overflow:auto!important;overscroll-behavior:contain!important;scrollbar-gutter:stable!important;
      border:1px solid #282c30!important;border-radius:12px!important;background:#151719!important;
      box-shadow:none!important;color:var(--h3s-text)!important;
      font:12px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important;
      contain:layout style paint!important;
    }
    .h3s-studio-panel *{box-sizing:border-box}
    .h3s-studio-panel::-webkit-scrollbar{width:8px}.h3s-studio-panel::-webkit-scrollbar-thumb{background:#34383d;border-radius:999px}
    .h3s-studio-header{
      position:sticky!important;top:0!important;z-index:6!important;min-height:50px!important;
      padding:0 16px!important;background:#151719!important;border-bottom:1px solid #24282c!important;
    }
    .h3s-studio-brand{gap:10px!important}.h3s-studio-mark{width:22px!important;height:22px!important;border-radius:7px!important;background:#252a30!important;box-shadow:none!important;position:relative}
    .h3s-studio-mark::after{content:'H3';position:absolute;inset:0;display:grid;place-items:center;color:#dfe5eb;font:800 8px/1 system-ui}
    .h3s-studio-title{font-size:13px!important;font-weight:720!important;letter-spacing:0!important}.h3s-status-pill{padding:3px 7px!important;border:0!important;border-radius:6px!important;background:#202327!important;color:#aeb4bb!important;font-size:9px!important;letter-spacing:0!important}

    .h3s-section{
      gap:10px!important;padding:15px 16px!important;border:0!important;border-bottom:1px solid #24282c!important;
      border-radius:0!important;background:transparent!important;box-shadow:none!important;
    }
    .h3s-section:last-child{border-bottom:0!important}.h3s-section-header{min-height:24px!important}.h3s-section-title{display:flex;align-items:center;gap:7px;color:#d8dcdf!important;font-size:11px!important;font-weight:700!important;letter-spacing:0!important;text-transform:none!important}
    .h3s-section-title[data-h3-icon]::before{content:attr(data-h3-icon);display:grid;place-items:center;width:19px;height:19px;border-radius:5px;background:#23272b;color:#c8cdd2;font:700 11px/1 system-ui}
    .h3s-section-description{margin:-3px 0 0!important;color:#858b91!important;font-size:10px!important;line-height:1.45!important;max-width:680px}.h3s-section-stack{gap:10px!important}.h3s-context-help{color:#858b91!important;font-size:10px!important;line-height:1.5!important}

    .h3s-grid{gap:10px!important;grid-template-columns:repeat(2,minmax(0,1fr))!important}.h3s-field{gap:5px!important}.h3s-field-label{margin:0!important;color:#969ca2!important;font-size:10px!important;font-weight:600!important;text-transform:none!important;letter-spacing:0!important}.h3s-field-hint{font-size:9px!important;color:#70767c!important}
    .h3s-control,.h3s-number,.h3s-writer-instruction,.h3s-reference-description{
      border:1px solid #30353a!important;border-radius:8px!important;background:#191c1f!important;color:#eef1f3!important;box-shadow:none!important;
    }
    .h3s-control{height:34px!important;padding:6px 9px!important}.h3s-control:hover,.h3s-number:hover,.h3s-writer-instruction:hover,.h3s-reference-description:hover{border-color:#454b51!important}.h3s-control:focus,.h3s-number:focus,.h3s-writer-instruction:focus,.h3s-reference-description:focus{outline:none!important;border-color:#718096!important;box-shadow:0 0 0 2px rgba(138,180,248,.10)!important}

    .h3s-choice{position:relative;width:100%;min-width:0}.h3s-choice-trigger{display:grid;grid-template-columns:minmax(0,1fr) 18px;align-items:center;gap:6px;width:100%;height:34px;padding:6px 8px 6px 10px;border:1px solid #30353a;border-radius:8px;background:#191c1f;color:#edf0f2;cursor:pointer;text-align:left;font:inherit}.h3s-choice-trigger:hover,.h3s-choice.is-open .h3s-choice-trigger{border-color:#4a5056;background:#1c1f22}.h3s-choice-trigger:focus-visible{outline:2px solid rgba(138,180,248,.18);outline-offset:1px}.h3s-choice-trigger:disabled{opacity:.42;cursor:default}.h3s-choice-value{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10.5px}.h3s-choice-chevron{display:grid;place-items:center;color:#858b91;font-size:13px}.h3s-choice.is-open .h3s-choice-chevron{transform:rotate(180deg)}
    .h3s-choice-menu{position:fixed;z-index:1000000;overflow:auto;padding:5px;border:1px solid #34393e;border-radius:9px;background:#1b1e21;box-shadow:0 10px 28px rgba(0,0,0,.35);color:#edf0f2;font:10.5px/1.3 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;backdrop-filter:none!important}.h3s-choice-option{display:block;width:100%;min-height:32px;padding:7px 9px;border:0;border-radius:6px;background:transparent;color:inherit;text-align:left;cursor:pointer;font:inherit;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.h3s-choice-option:hover,.h3s-choice-option:focus{outline:none;background:#262a2e}.h3s-choice-option.is-active{background:#252b32;color:#f1f4f7}.h3s-choice-option.is-active::before{content:'✓';display:inline-block;width:18px;color:#a9b9cd}

    .h3s-resolution-presets{gap:5px!important}.h3s-resolution-preset,.h3s-resolution-mode{min-height:27px!important;padding:4px 8px!important;border:1px solid #30353a!important;border-radius:7px!important;background:#191c1f!important;color:#939aa1!important;font-size:9px!important}.h3s-resolution-preset:hover,.h3s-resolution-mode:hover{border-color:#484e54!important;color:#e6eaed!important}.h3s-resolution-preset.is-active,.h3s-resolution-mode.is-active{border-color:#59616a!important;background:#282d32!important;color:#f0f2f4!important;box-shadow:none!important}.h3s-resolution-preview{min-height:50px!important;padding:8px 10px!important;border:1px solid #2b3035!important;border-radius:9px!important;background:#181b1e!important}.h3s-megapixel-control .h3s-range-track::before{background:#858f9b!important}.h3s-megapixel-control .h3s-range-thumb{background:#d0d5da!important;box-shadow:none!important}

    .h3s-switch{min-height:30px!important;font-size:10.5px!important}.h3s-switch-track{width:32px!important;height:18px!important;border-color:#3a3f44!important;background:#202327!important}.h3s-switch-track::after{width:12px!important;height:12px!important;background:#7e858c!important}.h3s-switch input:checked + .h3s-switch-track{border-color:#5b6672!important;background:#38414b!important}.h3s-switch input:checked + .h3s-switch-track::after{transform:translateX(14px)!important;background:#d7dce1!important}

    .h3s-reference-list{gap:8px!important}.h3s-reference-card{display:grid!important;grid-template-columns:minmax(82px,108px) minmax(0,1fr)!important;gap:12px!important;padding:10px!important;border:1px solid #2b3035!important;border-radius:10px!important;background:#181b1e!important;box-shadow:none!important}.h3s-reference-card-auto{border-color:#343a40!important}.h3s-reference-thumb{min-height:88px!important;border:0!important;border-radius:8px!important;background:#22262a!important;overflow:hidden!important}.h3s-reference-thumb img{width:100%!important;height:100%!important;object-fit:cover!important}.h3s-reference-index{left:6px!important;bottom:6px!important;top:auto!important;padding:3px 6px!important;border:0!important;border-radius:5px!important;background:rgba(17,19,21,.82)!important;color:#f0f2f4!important;font-size:9px!important}.h3s-reference-body{gap:7px!important}.h3s-reference-top{min-height:25px!important}.h3s-reference-name{font-size:11px!important;font-weight:650!important}.h3s-reference-source{color:#747b82!important;font-size:9px!important}.h3s-reference-controls{grid-template-columns:1fr 1fr!important;gap:7px!important}.h3s-reference-description{min-height:64px!important;padding:8px 9px!important;font-size:10px!important;line-height:1.45!important;resize:vertical!important}.h3s-reference-help{color:#777e85!important;font-size:9px!important;line-height:1.4!important}.h3s-auto-role{width:max-content;max-width:100%;padding:3px 6px!important;border:0!important;border-radius:5px!important;background:#24282c!important;color:#a8afb6!important;font-size:8.5px!important}.h3s-reference-actions{gap:2px!important}.h3s-icon-button{width:27px!important;height:27px!important;border:0!important;border-radius:6px!important;background:transparent!important;color:#8f969d!important}.h3s-icon-button:hover{background:#25292d!important;color:#edf0f2!important}.h3s-danger:hover{background:#352426!important;color:#efb4b8!important}.h3s-add-image{min-height:30px!important;padding:5px 10px!important;border:1px solid #343a40!important;border-radius:8px!important;background:#202429!important;color:#e7eaed!important;font-size:10px!important}.h3s-add-image:hover{background:#282d32!important;border-color:#444a50!important}

    .h3s-prompt-studio{padding-top:8px!important;border-top:1px solid #262a2e!important}.h3s-prompt-studio>summary{color:#9aa0a6!important;font-size:10px!important}.h3s-writer-instruction{min-height:64px!important;padding:8px 9px!important}.h3s-result{border:1px solid #2b3035!important;border-radius:9px!important;background:#181b1e!important}.h3s-result>summary{padding:9px 10px!important}.h3s-result-label{border:0!important;border-radius:5px!important;background:#24282c!important;color:#aeb4ba!important}.h3s-result-prompt{background:#16191b!important;border-top:1px solid #25292d!important}

    .h3s-final-result{border:1px solid #2b3035!important;border-radius:10px!important;background:#181b1e!important}.h3s-output-stage{background:#101214!important}.h3s-final-action,.h3s-output-tab,.h3s-copy-result{border:1px solid #30353a!important;border-radius:7px!important;background:#1c2023!important;color:#dce0e3!important;box-shadow:none!important}.h3s-final-action:hover,.h3s-output-tab:hover,.h3s-copy-result:hover{background:#252a2e!important;border-color:#454b51!important}.h3s-output-tab.is-active{background:#2a3036!important;border-color:#4a525a!important;color:#fff!important}

    .h3s-runtime-section{background:transparent!important}.h3rt{gap:10px!important}.h3rt-copy p{font-size:10px!important;color:#858b91!important}.h3rt-detect,.h3rt-reset{border:1px solid #30353a!important;border-radius:7px!important;background:#1b1e21!important;color:#cbd0d4!important;box-shadow:none!important}.h3rt-presets{grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:6px!important}.h3rt-preset{min-height:54px!important;padding:8px 9px!important;border:1px solid #2d3237!important;border-radius:8px!important;background:#181b1e!important;color:#e6e9eb!important;box-shadow:none!important;transform:none!important}.h3rt-preset:hover{border-color:#454b51!important;background:#1e2225!important;transform:none!important}.h3rt-preset.is-active{border-color:#56606a!important;background:#272c31!important;box-shadow:none!important}.h3rt-preset-name{font-size:10.5px!important}.h3rt-preset-sub,.h3rt-preset.is-active .h3rt-preset-sub{color:#81888f!important;font-size:8.5px!important}.h3rt-chip{padding:7px 8px!important;border:0!important;border-radius:7px!important;background:#1d2023!important}.h3rt-result{padding:10px!important;border:1px solid #2d3237!important;border-radius:9px!important;background:#181b1e!important}.h3rt-result-tag{color:#8f969d!important}.h3rt-warning{color:#d6b27a!important}.h3rt-expert{border-top:1px solid #262a2e!important}

    /* Smart Benchmark — experiment editor, not a neon dashboard. */
    .h3b4{--b-bg:#151719!important;--b-surface:#1b1e21!important;--b-raised:#22262a!important;--b-border:#2c3034!important;--b-text:#f0f2f4!important;--b-muted:#8d949a!important;--b-accent:#8ab4f8!important;width:100%!important;max-width:100%!important;max-height:720px!important;padding:0!important;border:1px solid #292d31!important;border-radius:12px!important;background:#151719!important;color:#f0f2f4!important;font:11px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important;box-shadow:none!important;contain:layout style paint!important}.h3b4-head{top:0!important;margin:0!important;padding:13px 14px!important;background:#151719!important;border-bottom:1px solid #25292d!important}.h3b4-title{font-size:13px!important;font-weight:720!important}.h3b4-sub{font-size:9.5px!important;color:#858c92!important}.h3b4-health{padding:3px 7px!important;border:0!important;border-radius:6px!important;background:#202428!important;color:#aeb5bb!important;font-size:8.5px!important}.h3b4-presets{padding:12px 14px 0!important;margin:0!important;gap:6px!important}.h3b4-preset{min-height:52px!important;padding:8px 9px!important;border:1px solid #2d3237!important;border-radius:8px!important;background:#191c1f!important;box-shadow:none!important;transform:none!important}.h3b4-preset:hover{border-color:#454b51!important;transform:none!important}.h3b4-preset.is-active{border-color:#59626b!important;background:#272c31!important;box-shadow:none!important}.h3b4-preset b{font-size:10px!important}.h3b4-preset span,.h3b4-preset.is-active span{color:#858c92!important;font-size:8.5px!important}.h3b4-toolbar{padding:9px 14px 0!important;margin:0!important}.h3b4-btn{min-height:31px!important;padding:6px 9px!important;border:1px solid #30353a!important;border-radius:7px!important;background:#1b1e21!important;color:#dfe3e6!important;font-size:9px!important}.h3b4-btn:hover{border-color:#484e54!important}.h3b4-btn.primary{border-color:#48515a!important;background:#252a2f!important}.h3b4-summary{margin:9px 14px!important;padding:8px 9px!important;border:0!important;border-radius:7px!important;background:#1c1f22!important;color:#8c9399!important;font-size:9px!important}.h3b4-list{padding:0 14px 14px!important;gap:8px!important}.h3b4-card{padding:11px!important;border:1px solid #2c3136!important;border-radius:9px!important;background:#181b1e!important;box-shadow:none!important}.h3b4-card-head{grid-template-columns:26px minmax(0,1fr) auto!important}.h3b4-index{width:26px!important;height:26px!important;border:0!important;border-radius:6px!important;background:#262a2e!important;color:#cbd0d4!important}.h3b4-name{height:31px!important;font-size:10.5px!important}.h3b4-label{font-size:8.5px!important;color:#858c92!important}.h3b4-input{height:32px!important;border:1px solid #30353a!important;border-radius:7px!important;background:#151719!important;color:#edf0f2!important;font-size:9.5px!important}.h3b4-input:focus{border-color:#59616a!important;box-shadow:0 0 0 2px rgba(138,180,248,.08)!important}.h3b4-pill{min-height:28px!important;padding:5px 8px!important;border:1px solid #30353a!important;border-radius:7px!important;background:#1b1e21!important;color:#939aa1!important;font-size:8.5px!important}.h3b4-pill:hover{border-color:#464c52!important;color:#e5e8ea!important}.h3b4-pill.is-active{border-color:#59616a!important;background:#282d32!important;color:#f0f2f4!important}.h3b4-lora{border:0!important;border-radius:7px!important;background:#202327!important}.h3b4-empty{border:1px dashed #33383d!important;border-radius:8px!important;color:#858c92!important;font-size:9.5px!important}

    .h3b4-parent-fix{overflow:visible!important;max-width:100%!important;width:100%!important}
    @media(max-width:760px){.h3s-grid,.h3s-reference-controls{grid-template-columns:1fr!important}.h3s-reference-card{grid-template-columns:80px minmax(0,1fr)!important}.h3rt-presets,.h3b4-presets{grid-template-columns:1fr 1fr!important}}
  `;
  document.head.append(style);
}

function forceHideNativeWidgets(node) {
  if (!node || node.comfyClass !== DIRECTOR) return;
  for (const widget of node.widgets || []) {
    if (!widget?.name || VISIBLE_NATIVE.has(widget.name)) continue;
    if (!widget.__h3studioV5Hidden) {
      widget.__h3studioV5Hidden = true;
      widget.__h3studioV5OriginalCompute = widget.computeSize;
      widget.__h3studioV5OriginalType = widget.type;
    }
    widget.hidden = true;
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
    if (widget.inputEl?.style) widget.inputEl.style.display = "none";
    if (widget.element?.style && widget.name !== "h3studio_controls") widget.element.style.display = "none";
  }
}

function decoratePanel(node) {
  const root = node?.__h3studioPanel;
  if (!root) return;
  root.style.contentVisibility = "auto";
  root.style.containIntrinsicSize = "780px";
  for (const title of root.querySelectorAll(".h3s-section-title")) {
    const text = String(title.textContent || "").trim();
    const icon = ICONS[text];
    if (icon) title.dataset.h3Icon = icon;
  }
  for (const button of root.querySelectorAll("button")) {
    const text = String(button.textContent || "").trim();
    if (button.dataset.h3Decorated) continue;
    if (/^\+ Add images$/i.test(text)) button.textContent = "＋  Add images";
    else if (/^Copy$/i.test(text)) button.textContent = "⧉  Copy";
    else if (/^New seed$/i.test(text)) button.textContent = "↻  New seed";
    else if (/^Same seed$/i.test(text)) button.textContent = "↺  Same seed";
    button.dataset.h3Decorated = "1";
  }
}

function optimizeDomWidget(node) {
  const widget = (node?.widgets || []).find((item) => item?.name === "h3studio_controls");
  if (!widget) return;
  widget.options ||= {};
  widget.options.hideOnZoom = true;
  widget.hideOnZoom = true;
  if (widget.element?.style) {
    widget.element.style.contain = "layout style paint";
    widget.element.style.contentVisibility = "auto";
  }
}

function attachDirector(node) {
  if (!node || node.comfyClass !== DIRECTOR) return;
  forceHideNativeWidgets(node);
  optimizeDomWidget(node);
  decoratePanel(node);
  if (node.__h3studioV5Guard) return;
  node.__h3studioV5Guard = true;

  /* Do not walk every widget on every canvas frame. The old v4 wrapper did
     exactly that and made large workflows noticeably sticky while panning. */
  const originalDraw = node.onDrawForeground;
  let lastDrawAt = 0;
  node.onDrawForeground = function h3studioV5DrawForeground() {
    const now = performance.now();
    if (now - lastDrawAt < DRAW_INTERVAL_MS) return;
    lastDrawAt = now;
    return originalDraw?.apply(this, arguments);
  };

  const originalResize = node.onResize;
  node.onResize = function h3studioV5Resize() {
    const result = originalResize?.apply(this, arguments);
    forceHideNativeWidgets(this);
    optimizeDomWidget(this);
    decoratePanel(this);
    return result;
  };

  const root = node.__h3studioPanel;
  if (root && !root.__h3studioV5Observer) {
    let queued = false;
    const observer = new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        decoratePanel(node);
        optimizeDomWidget(node);
      });
    });
    observer.observe(root, { childList: true, subtree: true });
    root.__h3studioV5Observer = observer;
  }
}

function fixBenchmark(node) {
  if (node?.comfyClass !== BENCHMARK) return;
  const root = node.__h3bRoot;
  if (root?.parentElement) root.parentElement.classList.add("h3b4-parent-fix");
  if (root) {
    root.style.contentVisibility = "auto";
    root.style.containIntrinsicSize = "680px";
  }
  const widget = (node.widgets || []).find((item) => item?.name === "h3studio_smart_benchmark");
  if (widget) {
    widget.options ||= {};
    widget.options.hideOnZoom = true;
    widget.hideOnZoom = true;
  }
}

function sweep() {
  for (const node of app.graph?._nodes || []) {
    if (node?.comfyClass === DIRECTOR) attachDirector(node);
    else if (node?.comfyClass === BENCHMARK) fixBenchmark(node);
  }
}

app.registerExtension({
  name: "H3Studio.ProductUIV5",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== DIRECTOR && nodeData.name !== BENCHMARK) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function h3studioProductCreated() {
      const result = created?.apply(this, arguments);
      requestAnimationFrame(() => nodeData.name === DIRECTOR ? attachDirector(this) : fixBenchmark(this));
      return result;
    };
    const configured = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function h3studioProductConfigured() {
      const result = configured?.apply(this, arguments);
      requestAnimationFrame(() => nodeData.name === DIRECTOR ? attachDirector(this) : fixBenchmark(this));
      return result;
    };
  },
  setup() { installStyles(); },
  afterConfigureGraph() { installStyles(); setTimeout(sweep, 80); },
  nodeCreated(node) {
    installStyles();
    if (node?.comfyClass === DIRECTOR) requestAnimationFrame(() => attachDirector(node));
    else if (node?.comfyClass === BENCHMARK) requestAnimationFrame(() => fixBenchmark(node));
  },
});