import { app } from "../../scripts/app.js";

const DIRECTOR = "H3StudioDirector";
const BENCHMARK = "H3StudioSmartBenchmark";
const STYLE_ID = "h3studio-product-ui-v6-style";
const VISIBLE_NATIVE = new Set(["prompt", "h3_prompt_mentions", "h3studio_controls"]);
const DRAW_INTERVAL_MS = 160;

const SECTION_ICONS = Object.freeze({
  generation: "◉",
  direction: "✦",
  references: "▧",
  runtime: "⚙",
  output: "↗",
  results: "⌁",
  advanced: "⋯",
  loras: "◇",
});

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    /* Product UI v6: quiet chrome, strong work surface, no card wall. */
    .h3s-studio-panel{
      --h3s-bg:#101214!important;
      --h3s-surface:#15181b!important;
      --h3s-surface-2:#191d21!important;
      --h3s-raised:#1e2227!important;
      --h3s-text:#eef1f3!important;
      --h3s-muted:#8b9299!important;
      --h3s-dim:#666d74!important;
      --h3s-border:#292e33!important;
      --h3s-border-soft:#22272b!important;
      --h3s-accent:#a8b7ca!important;
      --h3s-warning:#d4ae74!important;
      display:block!important;
      width:100%;max-width:100%;height:100%;min-width:0;
      padding:0!important;overflow:auto!important;overscroll-behavior:contain!important;
      scrollbar-gutter:stable!important;box-sizing:border-box!important;
      border:1px solid #262b30!important;border-radius:10px!important;
      background:#101214!important;color:var(--h3s-text)!important;box-shadow:none!important;
      font:12px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important;
      contain:layout style paint!important;
    }
    .h3s-studio-panel *{box-sizing:border-box;min-width:0}
    .h3s-studio-panel::-webkit-scrollbar{width:8px}.h3s-studio-panel::-webkit-scrollbar-thumb{background:#30353a;border:2px solid #101214;border-radius:999px}

    .h3s-studio-header{
      position:sticky!important;top:0!important;z-index:20!important;display:flex!important;align-items:center!important;
      min-height:46px!important;padding:0 14px!important;margin:0!important;
      border:0!important;border-bottom:1px solid #23282d!important;background:rgba(16,18,20,.97)!important;
      backdrop-filter:none!important;
    }
    .h3s-studio-brand{display:flex!important;align-items:center!important;gap:8px!important}.h3s-studio-mark{position:relative!important;width:18px!important;height:18px!important;border:0!important;border-radius:4px!important;background:transparent!important;box-shadow:none!important}.h3s-studio-mark::after{content:'△';position:absolute;inset:0;display:grid;place-items:center;color:#cfd5da;font:700 15px/1 system-ui}.h3s-studio-title{font-size:12px!important;font-weight:700!important;letter-spacing:0!important}.h3s-status-pill{padding:2px 6px!important;border:0!important;border-radius:5px!important;background:#1b1f23!important;color:#8e969d!important;font-size:8px!important;letter-spacing:.02em!important}

    .h3s-v6-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(286px,34%);align-items:start;min-height:100%;background:#101214}
    .h3s-v6-main{min-width:0;padding:4px 18px 18px;background:#101214}
    .h3s-v6-inspector{min-width:0;padding:4px 14px 18px;border-left:1px solid #24292e;background:#121416;align-self:stretch}

    .h3s-section{display:block!important;margin:0!important;padding:18px 0!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;overflow:visible!important}
    .h3s-v6-main>.h3s-section+.h3s-section,.h3s-v6-inspector>.h3s-section+.h3s-section{border-top:1px solid #22272b!important}
    .h3s-section-header{display:flex!important;align-items:center!important;justify-content:space-between!important;min-height:24px!important;margin:0 0 9px!important;gap:8px!important}
    .h3s-section-title{display:flex!important;align-items:center!important;gap:7px!important;color:#dce1e5!important;font-size:11px!important;font-weight:690!important;text-transform:none!important;letter-spacing:0!important}
    .h3s-section-title[data-h3-icon]::before{content:attr(data-h3-icon);display:inline-grid;place-items:center;width:15px;height:15px;color:#858e97;font:600 11px/1 system-ui}
    .h3s-section-description{margin:-3px 0 10px!important;max-width:680px!important;color:#737b83!important;font-size:9.5px!important;line-height:1.45!important}
    .h3s-section-stack{display:flex!important;flex-direction:column!important;gap:9px!important}
    .h3s-context-help{margin:0!important;color:#747c84!important;font-size:9px!important;line-height:1.45!important}

    /* Main workspace: Direction and References are the actual product. */
    .h3s-v6-main [data-h3-section="direction"]{padding-top:15px!important}
    .h3s-v6-main [data-h3-section="direction"]>.h3s-section-header{margin-bottom:5px!important}
    .h3s-v6-main [data-h3-section="direction"]>.h3s-section-description{margin-bottom:12px!important}
    .h3s-v6-main [data-h3-section="direction"] .h3s-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:8px 12px!important;padding:0!important;border:0!important;background:transparent!important}
    .h3s-v6-main [data-h3-section="direction"] .h3s-context-help{display:none!important}
    .h3s-v6-main [data-h3-section="direction"] .h3s-prompt-studio{margin-top:2px!important;padding-top:8px!important;border-top:1px solid #22272b!important}
    .h3s-prompt-studio>summary{padding:4px 0!important;color:#8b939a!important;font-size:9px!important}
    .h3s-writer-instruction{min-height:72px!important;padding:9px!important}

    .h3s-field{display:flex!important;flex-direction:column!important;gap:4px!important;margin:0!important}.h3s-field-label{margin:0!important;color:#737b82!important;font-size:8.5px!important;font-weight:600!important;text-transform:none!important;letter-spacing:0!important}.h3s-field-hint{font-size:8px!important;color:#626a71!important}
    .h3s-control,.h3s-number,.h3s-writer-instruction,.h3s-reference-description{border:1px solid #2d3338!important;border-radius:6px!important;background:#15181b!important;color:#e8ecef!important;box-shadow:none!important}.h3s-control{height:32px!important;padding:5px 8px!important}.h3s-control:hover,.h3s-number:hover,.h3s-writer-instruction:hover,.h3s-reference-description:hover{border-color:#42494f!important}.h3s-control:focus,.h3s-number:focus,.h3s-writer-instruction:focus,.h3s-reference-description:focus{outline:none!important;border-color:#65717d!important;box-shadow:0 0 0 2px rgba(168,183,202,.08)!important}

    .h3s-choice{position:relative;width:100%;min-width:0}.h3s-choice-trigger{display:grid;grid-template-columns:minmax(0,1fr) 16px;align-items:center;gap:5px;width:100%;height:32px;padding:5px 7px 5px 9px;border:1px solid #2d3338;border-radius:6px;background:#15181b;color:#e8ecef;cursor:pointer;text-align:left;font:inherit}.h3s-choice-trigger:hover,.h3s-choice.is-open .h3s-choice-trigger{border-color:#444b51;background:#181c20}.h3s-choice-trigger:focus-visible{outline:2px solid rgba(168,183,202,.14);outline-offset:1px}.h3s-choice-trigger:disabled{opacity:.38;cursor:default}.h3s-choice-value{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px}.h3s-choice-chevron{display:grid;place-items:center;color:#747c84;font-size:12px}.h3s-choice.is-open .h3s-choice-chevron{transform:rotate(180deg)}
    .h3s-choice-menu{position:fixed;z-index:1000000;overflow:auto;padding:4px;border:1px solid #353b41;border-radius:7px;background:#181b1e;box-shadow:0 12px 30px rgba(0,0,0,.38);color:#ebedef;font:10px/1.3 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;backdrop-filter:none!important}.h3s-choice-option{display:block;width:100%;min-height:30px;padding:6px 8px;border:0;border-radius:5px;background:transparent;color:inherit;text-align:left;cursor:pointer;font:inherit;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.h3s-choice-option:hover,.h3s-choice-option:focus{outline:none;background:#23272b}.h3s-choice-option.is-active{background:#252a2f;color:#f4f6f7}.h3s-choice-option.is-active::before{content:'✓';display:inline-block;width:17px;color:#aebbc8}

    .h3s-switch{min-height:28px!important;font-size:10px!important}.h3s-switch-track{width:30px!important;height:17px!important;border:1px solid #343a40!important;background:#1d2125!important}.h3s-switch-track::after{width:11px!important;height:11px!important;background:#777f87!important}.h3s-switch input:checked + .h3s-switch-track{border-color:#59636d!important;background:#353d45!important}.h3s-switch input:checked + .h3s-switch-track::after{transform:translateX(13px)!important;background:#d5dbe0!important}

    /* Reference cards become rows, not cards. */
    .h3s-reference-list{display:flex!important;flex-direction:column!important;gap:0!important;border-top:1px solid #22272b!important}
    .h3s-reference-card{display:grid!important;grid-template-columns:92px minmax(0,1fr)!important;gap:12px!important;margin:0!important;padding:12px 0!important;border:0!important;border-bottom:1px solid #22272b!important;border-radius:0!important;background:transparent!important;box-shadow:none!important}
    .h3s-reference-card-auto{border-color:#22272b!important}.h3s-reference-thumb{height:86px!important;min-height:86px!important;border:0!important;border-radius:6px!important;background:#1a1e22!important;overflow:hidden!important}.h3s-reference-thumb img{width:100%!important;height:100%!important;object-fit:cover!important}.h3s-reference-index{left:5px!important;bottom:5px!important;top:auto!important;padding:2px 5px!important;border:0!important;border-radius:4px!important;background:rgba(12,14,16,.82)!important;color:#e5e9ec!important;font-size:8px!important}.h3s-reference-body{display:flex!important;flex-direction:column!important;gap:6px!important}.h3s-reference-top{display:flex!important;align-items:center!important;justify-content:space-between!important;min-height:22px!important}.h3s-reference-name{font-size:10.5px!important;font-weight:650!important}.h3s-reference-source{color:#666e75!important;font-size:8px!important}.h3s-reference-controls{display:grid!important;grid-template-columns:1fr 1fr!important;gap:7px!important}.h3s-reference-description{min-height:58px!important;padding:7px 8px!important;font-size:9.5px!important;line-height:1.4!important;resize:vertical!important}.h3s-reference-help{display:none!important}.h3s-auto-role{width:max-content;max-width:100%;padding:2px 5px!important;border:0!important;border-radius:4px!important;background:#1b1f23!important;color:#818991!important;font-size:8px!important}.h3s-reference-actions{display:flex!important;gap:1px!important}.h3s-icon-button{width:25px!important;height:25px!important;border:0!important;border-radius:5px!important;background:transparent!important;color:#777f87!important}.h3s-icon-button:hover{background:#20252a!important;color:#e9ecee!important}.h3s-danger:hover{background:#302124!important;color:#e5afb4!important}.h3s-add-image{min-height:28px!important;padding:4px 8px!important;border:1px solid #343a40!important;border-radius:6px!important;background:#181c20!important;color:#d9dde0!important;font-size:9px!important}.h3s-add-image:hover{background:#20252a!important;border-color:#464d53!important}.h3s-empty{border:0!important;border-bottom:1px solid #22272b!important;border-radius:0!important;background:transparent!important;padding:18px 2px!important}

    /* Inspector: compact property sheet, not a second dashboard. */
    .h3s-v6-inspector .h3s-section{padding:14px 0!important}.h3s-v6-inspector .h3s-section-header{margin-bottom:8px!important}.h3s-v6-inspector .h3s-grid{display:grid!important;grid-template-columns:1fr!important;gap:8px!important;padding:0!important;border:0!important;background:transparent!important}.h3s-v6-inspector .h3s-field{display:grid!important;grid-template-columns:82px minmax(0,1fr)!important;align-items:center!important;gap:8px!important}.h3s-v6-inspector .h3s-field-label{align-self:center!important}.h3s-v6-inspector .h3s-context-help{display:none!important}.h3s-v6-inspector .h3s-resolution-modes{display:grid!important;grid-template-columns:1fr 1fr!important;gap:4px!important}.h3s-resolution-mode,.h3s-resolution-preset{min-height:25px!important;padding:3px 6px!important;border:1px solid #2d3338!important;border-radius:5px!important;background:#15181b!important;color:#7f878e!important;font-size:8px!important}.h3s-resolution-mode:hover,.h3s-resolution-preset:hover{border-color:#42494f!important;color:#e1e5e8!important}.h3s-resolution-mode.is-active,.h3s-resolution-preset.is-active{border-color:#505a64!important;background:#22272c!important;color:#eef1f3!important;box-shadow:none!important}.h3s-resolution-presets{gap:4px!important}.h3s-resolution-preview{min-height:42px!important;padding:7px 8px!important;border:0!important;border-radius:6px!important;background:#171a1d!important}.h3s-resolution-result strong{font-size:11px!important}.h3s-resolution-result span,.h3s-resolution-note{font-size:8px!important}.h3s-resolution-tier{border:0!important;background:#20252a!important;color:#90989f!important}.h3s-megapixel-control .h3s-range-track::before{background:#78838e!important}.h3s-megapixel-control .h3s-range-thumb{background:#d0d5d9!important;box-shadow:none!important}

    /* Runtime becomes a compact segmented inspector. */
    .h3s-runtime-section{overflow:visible!important}.h3rt{gap:8px!important}.h3rt-copy{align-items:center!important}.h3rt-copy p{display:none!important}.h3rt-detect,.h3rt-reset{border:1px solid #2f353a!important;border-radius:6px!important;background:#171a1d!important;color:#afb5bb!important;box-shadow:none!important;padding:5px 7px!important;font-size:8px!important}.h3rt-presets{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:4px!important}.h3rt-preset{display:grid!important;grid-template-columns:18px minmax(0,1fr)!important;grid-template-rows:auto auto!important;align-items:center!important;min-height:42px!important;padding:6px 7px!important;border:1px solid #2b3136!important;border-radius:6px!important;background:#15181b!important;color:#e5e8ea!important;box-shadow:none!important;transform:none!important}.h3rt-preset::before{content:attr(data-h3-runtime-icon);grid-row:1/3;display:grid;place-items:center;width:16px;color:#858e96;font:600 11px/1 system-ui}.h3rt-preset:hover{border-color:#41484e!important;background:#191d21!important;transform:none!important}.h3rt-preset.is-active{border-color:#515b65!important;background:#22272c!important;box-shadow:none!important}.h3rt-preset-name{font-size:9.5px!important}.h3rt-preset-sub,.h3rt-preset.is-active .h3rt-preset-sub{margin-top:0!important;color:#737b82!important;font-size:7.5px!important}.h3rt-status{display:grid!important;grid-template-columns:1fr!important;gap:3px!important}.h3rt-chip{display:grid!important;grid-template-columns:58px minmax(0,1fr)!important;align-items:center!important;padding:5px 6px!important;border:0!important;border-radius:5px!important;background:#171a1d!important}.h3rt-chip b{font-size:7px!important;letter-spacing:.04em!important}.h3rt-chip span{margin:0!important;font-size:8.5px!important}.h3rt-result{padding:7px 8px!important;border:0!important;border-radius:6px!important;background:#171a1d!important}.h3rt-result-head strong{font-size:9.5px!important}.h3rt-result-tag{font-size:7px!important;color:#838c94!important}.h3rt-result-grid{grid-template-columns:1fr 1fr!important;gap:5px 8px!important;margin-top:6px!important}.h3rt-kv small{font-size:7px!important}.h3rt-kv span{font-size:8.5px!important}.h3rt-reason{font-size:8px!important}.h3rt-warning{font-size:8px!important;color:#c9a977!important}.h3rt-expert{padding-top:6px!important;border-top:1px solid #22272b!important}.h3rt-expert>summary{font-size:8.5px!important}.h3rt-expert-grid{grid-template-columns:1fr!important;gap:6px!important}.h3rt-expert-note{font-size:8px!important}

    .h3s-advanced-toggle{width:100%!important;padding:3px 0!important;border:0!important;background:transparent!important;color:#858d94!important;font-size:9px!important;text-align:left!important}.h3s-advanced-content{padding-top:8px!important}.h3s-final-result,.h3s-result{border:0!important;border-radius:7px!important;background:#15181b!important}.h3s-output-stage{background:#0c0e10!important;border-radius:6px!important}.h3s-final-action,.h3s-output-tab,.h3s-copy-result{border:1px solid #30363b!important;border-radius:5px!important;background:#171a1d!important;color:#cfd4d8!important;box-shadow:none!important}.h3s-final-action:hover,.h3s-output-tab:hover,.h3s-copy-result:hover{background:#20252a!important;border-color:#444b51!important}.h3s-output-tab.is-active{background:#252a2f!important;border-color:#4a535b!important;color:#fff!important}

    /* Benchmark: NEVER own the outer overlay width. ComfyUI's tracked root does. */
    .h3b4{--b-bg:#111315!important;--b-surface:#171a1d!important;--b-raised:#1d2125!important;--b-border:#2b3035!important;--b-text:#eef1f3!important;--b-muted:#858d94!important;--b-accent:#a8b7ca!important;min-width:0!important;box-sizing:border-box!important;max-height:560px!important;overflow-y:auto!important;overflow-x:hidden!important;padding:0!important;border:1px solid #292e33!important;border-radius:9px!important;background:#111315!important;color:#eef1f3!important;box-shadow:none!important;font:10px/1.4 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important;contain:layout paint!important}
    .h3b4-head{top:0!important;margin:0!important;padding:12px 13px!important;background:#111315!important;border-bottom:1px solid #24292e!important}.h3b4-title{font-size:12px!important;font-weight:700!important}.h3b4-sub{font-size:8.5px!important;color:#7b838a!important}.h3b4-health{padding:2px 6px!important;border:0!important;border-radius:5px!important;background:#1c2024!important;color:#929aa1!important;font-size:7.5px!important}.h3b4-presets{padding:10px 12px 0!important;margin:0!important;gap:4px!important}.h3b4-preset{min-height:44px!important;padding:6px 7px!important;border:1px solid #2b3136!important;border-radius:6px!important;background:#16191c!important;box-shadow:none!important;transform:none!important}.h3b4-preset:hover{border-color:#41484e!important;transform:none!important}.h3b4-preset.is-active{border-color:#505a63!important;background:#22272c!important;box-shadow:none!important}.h3b4-preset b{font-size:9px!important}.h3b4-preset span,.h3b4-preset.is-active span{color:#747c83!important;font-size:7.5px!important}.h3b4-toolbar{padding:8px 12px 0!important;margin:0!important}.h3b4-btn{min-height:28px!important;padding:5px 7px!important;border:1px solid #30363b!important;border-radius:5px!important;background:#171a1d!important;color:#d7dbde!important;font-size:8px!important}.h3b4-btn:hover{border-color:#454c52!important}.h3b4-btn.primary{border-color:#46505a!important;background:#20252a!important}.h3b4-summary{margin:8px 12px!important;padding:6px 7px!important;border:0!important;border-radius:5px!important;background:#171a1d!important;color:#7d858c!important;font-size:8px!important}.h3b4-list{padding:0 12px 12px!important;gap:0!important}.h3b4-card{padding:10px 0!important;border:0!important;border-top:1px solid #24292e!important;border-radius:0!important;background:transparent!important;box-shadow:none!important}.h3b4-card-head{grid-template-columns:24px minmax(0,1fr) auto!important}.h3b4-index{width:24px!important;height:24px!important;border:0!important;border-radius:5px!important;background:#20252a!important;color:#b8c0c7!important}.h3b4-name{height:29px!important;font-size:9.5px!important}.h3b4-label{font-size:7.5px!important;color:#747c83!important}.h3b4-input{height:30px!important;border:1px solid #2d3338!important;border-radius:5px!important;background:#131619!important;color:#e8ebed!important;font-size:8.5px!important}.h3b4-input:focus{border-color:#525d67!important;box-shadow:0 0 0 2px rgba(168,183,202,.07)!important}.h3b4-pill{min-height:25px!important;padding:4px 6px!important;border:1px solid #2c3237!important;border-radius:5px!important;background:#16191c!important;color:#7e868d!important;font-size:7.5px!important}.h3b4-pill:hover{border-color:#444b51!important;color:#e3e6e8!important}.h3b4-pill.is-active{border-color:#515a63!important;background:#22272c!important;color:#edf0f2!important}.h3b4-lora{border:0!important;border-radius:5px!important;background:#191d20!important}.h3b4-empty{border:0!important;border-top:1px solid #24292e!important;border-radius:0!important;color:#7c848b!important;font-size:8.5px!important}

    @media(max-width:760px){.h3s-v6-layout{grid-template-columns:1fr}.h3s-v6-inspector{border-left:0;border-top:1px solid #24292e}.h3s-v6-main [data-h3-section="direction"] .h3s-grid{grid-template-columns:1fr}.h3s-reference-card{grid-template-columns:78px minmax(0,1fr)!important}.h3b4-presets{grid-template-columns:1fr 1fr!important}}
  `;
  document.head.append(style);
}

function forceHideNativeWidgets(node) {
  if (!node || node.comfyClass !== DIRECTOR) return;
  for (const widget of node.widgets || []) {
    if (!widget?.name || VISIBLE_NATIVE.has(widget.name)) continue;
    if (!widget.__h3studioV6Hidden) {
      widget.__h3studioV6Hidden = true;
      widget.__h3studioV6OriginalCompute = widget.computeSize;
      widget.__h3studioV6OriginalType = widget.type;
    }
    widget.hidden = true;
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
    if (widget.inputEl?.style) widget.inputEl.style.display = "none";
    if (widget.element?.style && widget.name !== "h3studio_controls") widget.element.style.display = "none";
  }
}

function sectionKey(section) {
  if (!section) return "";
  if (section.classList.contains("h3s-runtime-section")) return "runtime";
  if (section.classList.contains("h3s-custom-loras")) return "loras";
  if (section.querySelector(":scope > .h3s-advanced-toggle")) return "advanced";
  const title = String(section.querySelector(":scope > .h3s-section-header .h3s-section-title")?.textContent || "").trim().toLowerCase();
  if (title === "generation") return "generation";
  if (title === "direction") return "direction";
  if (title === "references") return "references";
  if (title === "runtime") return "runtime";
  if (title === "generated output") return "output";
  if (title.includes("result")) return "results";
  return title.replace(/[^a-z0-9]+/g, "-") || "misc";
}

function decorateSections(root) {
  for (const section of root.querySelectorAll(".h3s-section")) {
    const key = sectionKey(section);
    section.dataset.h3Section = key;
    const title = section.querySelector(":scope > .h3s-section-header .h3s-section-title");
    if (title && SECTION_ICONS[key]) title.dataset.h3Icon = SECTION_ICONS[key];
  }
}

function placeDirectorSections(root) {
  if (!root) return;
  let layout = root.querySelector(":scope > .h3s-v6-layout");
  if (!layout) {
    layout = document.createElement("div");
    layout.className = "h3s-v6-layout";
    const main = document.createElement("div");
    main.className = "h3s-v6-main";
    const inspector = document.createElement("aside");
    inspector.className = "h3s-v6-inspector";
    layout.append(main, inspector);
    root.append(layout);
  }
  const main = layout.querySelector(":scope > .h3s-v6-main");
  const inspector = layout.querySelector(":scope > .h3s-v6-inspector");
  if (!main || !inspector) return;

  for (const section of [...root.querySelectorAll(":scope > .h3s-section")]) {
    const key = sectionKey(section);
    section.dataset.h3Section = key;
    const target = ["generation", "runtime", "advanced", "loras"].includes(key) ? inspector : main;
    if (key === "runtime") {
      for (const old of [...inspector.querySelectorAll(":scope > .h3s-runtime-section")]) {
        if (old !== section) old.remove();
      }
    }
    target.append(section);
  }
}

function decorateRuntime(root) {
  const icons = { auto: "◎", fast: "⚡", quality: "◇", low_vram: "▤", og_current: "○", extreme_low_vram: "▥" };
  for (const button of root.querySelectorAll(".h3rt-preset")) {
    const key = String(button.dataset.runtimePreset || "");
    button.dataset.h3RuntimeIcon = icons[key] || "·";
  }
}

function decorateButtons(root) {
  for (const button of root.querySelectorAll("button")) {
    const text = String(button.textContent || "").trim();
    if (button.dataset.h3DecoratedV6) continue;
    if (/^\+ Add images$/i.test(text)) button.textContent = "＋  Add images";
    else if (/^Copy$/i.test(text)) button.textContent = "⧉  Copy";
    else if (/^New seed$/i.test(text)) button.textContent = "↻  New seed";
    else if (/^Same seed$/i.test(text)) button.textContent = "↺  Same seed";
    button.dataset.h3DecoratedV6 = "1";
  }
}

function optimizeDirectorDomWidget(node) {
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

function decoratePanel(node) {
  const root = node?.__h3studioPanel;
  if (!root) return;
  root.style.contentVisibility = "auto";
  root.style.containIntrinsicSize = "820px";
  decorateSections(root);
  placeDirectorSections(root);
  decorateSections(root);
  decorateRuntime(root);
  decorateButtons(root);
  optimizeDirectorDomWidget(node);
}

function attachDirector(node) {
  if (!node || node.comfyClass !== DIRECTOR) return;
  forceHideNativeWidgets(node);
  decoratePanel(node);
  if (node.__h3studioV6Guard) return;
  node.__h3studioV6Guard = true;

  const originalDraw = node.onDrawForeground;
  let lastDrawAt = 0;
  node.onDrawForeground = function h3studioV6DrawForeground() {
    const now = performance.now();
    if (now - lastDrawAt < DRAW_INTERVAL_MS) return;
    lastDrawAt = now;
    return originalDraw?.apply(this, arguments);
  };

  const originalResize = node.onResize;
  node.onResize = function h3studioV6Resize() {
    const result = originalResize?.apply(this, arguments);
    forceHideNativeWidgets(this);
    decoratePanel(this);
    return result;
  };

  const root = node.__h3studioPanel;
  if (root && !root.__h3studioV6Observer) {
    let queued = false;
    const observer = new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        decoratePanel(node);
      });
    });
    observer.observe(root, { childList: true, subtree: true });
    root.__h3studioV6Observer = observer;
  }
}

function fixBenchmark(node) {
  if (node?.comfyClass !== BENCHMARK) return;
  const root = node.__h3bRoot;
  if (root?.parentElement) root.parentElement.classList.remove("h3b4-parent-fix");
  if (root) {
    /* Do not set width/max-width here. The stable-root guard and ComfyUI canvas
       renderer own the overlay's exact pixel width and transform at every zoom. */
    root.style.removeProperty("width");
    root.style.removeProperty("max-width");
    root.style.setProperty("min-width", "0", "important");
    root.style.setProperty("overflow-x", "hidden", "important");
    root.style.setProperty("max-height", "560px", "important");
    root.style.contentVisibility = "auto";
    root.style.containIntrinsicSize = "560px";
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
  name: "H3Studio.ProductUIV6",
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