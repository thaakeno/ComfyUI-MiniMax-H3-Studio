let installed = false;

export function installTheme() {
  if (installed || typeof document === "undefined") return;
  installed = true;
  const style = document.createElement("style");
  style.dataset.h3studio = "theme-v1";
  style.textContent = `
    .h3s-studio-panel {
      --h3s-bg: var(--component-node-widget-background, var(--comfy-input-bg, #202226));
      --h3s-surface: color-mix(in srgb, var(--h3s-bg) 94%, white 6%);
      --h3s-raised: color-mix(in srgb, var(--h3s-bg) 86%, white 14%);
      --h3s-text: var(--component-node-foreground, var(--input-text, #eceef2));
      --h3s-muted: var(--component-node-foreground-secondary, #9ca3af);
      --h3s-border: var(--border-default, rgba(255,255,255,.13));
      --h3s-accent: #34d3b5;
      --h3s-warning: #e6ad55;
      display: flex; flex-direction: column; gap: 7px; width: 100%; height: 100%; min-height: 0;
      box-sizing: border-box; padding: 9px; overflow: auto; overscroll-behavior: contain;
      color: var(--h3s-text); background: color-mix(in srgb, var(--h3s-bg) 97%, black 3%); border: 1px solid var(--h3s-border); border-radius: 8px;
      font: 12px/1.4 Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    }
    .h3s-studio-panel *, .h3s-studio-panel *::before, .h3s-studio-panel *::after { box-sizing: border-box; }
    .h3s-studio-header { position: sticky; top: -9px; z-index: 4; display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 30px; padding: 3px 1px; background: color-mix(in srgb, var(--h3s-bg) 97%, black 3%); }
    .h3s-studio-brand { display: flex; align-items: center; gap: 8px; min-width: 0; }
    .h3s-studio-mark { width: 4px; height: 16px; border-radius: 999px; background: var(--h3s-accent); }
    .h3s-studio-title { overflow: hidden; color: var(--h3s-text); font-size: 12px; font-weight: 680; letter-spacing: .01em; text-overflow: ellipsis; white-space: nowrap; }
    .h3s-status-pill { flex: none; padding: 2px 7px; border: 1px solid var(--h3s-border); border-radius: 999px; color: var(--h3s-muted); background: transparent; font-size: 9px; }
    .h3s-reference-heading-actions { display: flex; align-items: center; gap: 5px; }
    .h3s-add-image { min-height: 25px; padding: 3px 8px; border: 1px solid color-mix(in srgb, var(--h3s-accent) 45%, var(--h3s-border)); border-radius: 6px; color: var(--h3s-text); background: color-mix(in srgb, var(--h3s-accent) 12%, var(--h3s-bg)); cursor: pointer; font: 650 10px/1.2 ui-sans-serif, system-ui; }
    .h3s-add-image:hover { background: color-mix(in srgb, var(--h3s-accent) 20%, var(--h3s-bg)); }
    .h3s-add-image:focus-visible { outline: 2px solid color-mix(in srgb, var(--h3s-accent) 70%, transparent); outline-offset: 1px; }
    .h3s-add-image:disabled { cursor: default; opacity: .45; }
    .h3s-upload-error { padding: 7px 8px; border: 1px solid color-mix(in srgb, #ff7f7f 45%, var(--h3s-border)); border-radius: 6px; color: #ffb0b0; background: color-mix(in srgb, #ff6b6b 9%, var(--h3s-bg)); font-size: 10px; }
    .h3s-section { display: flex; flex-direction: column; gap: 6px; padding: 8px; border: 1px solid var(--h3s-border); border-radius: 7px; background: var(--h3s-surface); }
    .h3s-section-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .h3s-section-title { color: var(--h3s-muted); font-size: 9px; font-weight: 720; letter-spacing: .09em; text-transform: uppercase; }
    .h3s-section-description { margin: -1px 0 1px; color: var(--h3s-muted); font-size: 10px; line-height: 1.45; }
    .h3s-section-stack { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
    .h3s-context-help { margin: 0; color: color-mix(in srgb, var(--h3s-muted) 90%, var(--h3s-text) 10%); font-size: 9px; line-height: 1.45; }
    .h3s-validation-error { margin: 0; padding: 6px 7px; border: 1px solid color-mix(in srgb, #ff7f7f 45%, var(--h3s-border)); border-radius: 5px; color: #ffb0b0; background: color-mix(in srgb, #ff6b6b 9%, var(--h3s-bg)); font-size: 9px; line-height: 1.4; }
    .h3s-validation-notice { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 7px; border: 1px solid color-mix(in srgb, #ff7f7f 45%, var(--h3s-border)); border-radius: 6px; color: #ffb0b0; background: color-mix(in srgb, #ff6b6b 9%, var(--h3s-bg)); }
    .h3s-validation-notice-copy { display: flex; flex: 1; flex-direction: column; gap: 2px; min-width: 0; font-size: 9px; line-height: 1.4; }
    .h3s-validation-notice-copy strong { color: #ffd0d0; font-size: 10px; }
    .h3s-validation-fix { flex: none; min-height: 25px; padding: 3px 7px; border: 1px solid color-mix(in srgb, #ff9a9a 55%, var(--h3s-border)); border-radius: 5px; color: #ffe1e1; background: color-mix(in srgb, #ff6b6b 16%, var(--h3s-bg)); cursor: pointer; font: 650 9px/1.2 ui-sans-serif, system-ui; }
    .h3s-validation-fix:hover { background: color-mix(in srgb, #ff6b6b 25%, var(--h3s-bg)); }
    .h3s-validation-fix:focus-visible { outline: 2px solid color-mix(in srgb, #ff9a9a 75%, transparent); outline-offset: 1px; }
    .h3s-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 6px; }
    .h3s-field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
    .h3s-field-label { color: var(--h3s-muted); font-size: 10px; font-weight: 600; }
    .h3s-field-hint { overflow: hidden; color: color-mix(in srgb, var(--h3s-muted) 75%, transparent); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
    .h3s-control { width: 100%; min-width: 0; height: 25px; padding: 3px 7px; border: 1px solid var(--h3s-border); border-radius: 5px; outline: none; color: var(--h3s-text); background: var(--h3s-bg); font: inherit; }
    .h3s-control:hover { border-color: color-mix(in srgb, var(--h3s-accent) 40%, var(--h3s-border)); }
    .h3s-control:focus-visible, .h3s-icon-button:focus-visible, .h3s-reference-description:focus-visible { outline: 2px solid color-mix(in srgb, var(--h3s-accent) 70%, transparent); outline-offset: 1px; }
    .h3s-seed-row { display: grid; grid-template-columns: minmax(0,1fr) 27px 27px; gap: 4px; }
    .h3s-seed-lock[aria-pressed="true"] { border-color: color-mix(in srgb, var(--h3s-accent) 65%, var(--h3s-border)); color: var(--h3s-accent); background: color-mix(in srgb, var(--h3s-accent) 12%, var(--h3s-bg)); }
    .h3s-range { --h3s-range-progress: 0%; position: relative; width: 100%; height: 16px; }
    .h3s-range-track { position: absolute; left: 0; right: 0; top: 50%; height: 3px; overflow: hidden; border-radius: 999px; background: var(--h3s-border); transform: translateY(-50%); pointer-events: none; }
    .h3s-range-track::before { content: ""; display: block; width: var(--h3s-range-progress); height: 100%; background: var(--h3s-accent); }
    .h3s-range-thumb { position: absolute; left: var(--h3s-range-progress); top: 50%; width: 13px; height: 13px; border: 2px solid var(--h3s-raised); border-radius: 999px; background: var(--h3s-accent); box-shadow: 0 1px 3px rgba(0,0,0,.35); transform: translate(-50%,-50%); pointer-events: none; }
    .h3s-range-native { position: absolute; inset: 0; z-index: 1; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; }
    .h3s-range:has(.h3s-range-native:focus-visible) { outline: 2px solid color-mix(in srgb, var(--h3s-accent) 70%, transparent); outline-offset: 1px; border-radius: 5px; }
    .h3s-inline-value { color: var(--h3s-text); font-variant-numeric: tabular-nums; }
    .h3s-switch { display: flex; align-items: center; gap: 7px; min-height: 25px; color: var(--h3s-text); cursor: pointer; font-size: 10px; }
    .h3s-switch input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
    .h3s-switch-track { position: relative; flex: none; width: 30px; height: 17px; border: 1px solid var(--h3s-border); border-radius: 999px; background: var(--h3s-bg); transition: background 120ms ease, border-color 120ms ease; }
    .h3s-switch-track::after { content: ""; position: absolute; left: 2px; top: 2px; width: 11px; height: 11px; border-radius: 999px; background: var(--h3s-muted); transition: transform 120ms ease, background 120ms ease; }
    .h3s-switch input:checked + .h3s-switch-track { border-color: color-mix(in srgb, var(--h3s-accent) 60%, var(--h3s-border)); background: color-mix(in srgb, var(--h3s-accent) 28%, var(--h3s-bg)); }
    .h3s-switch input:checked + .h3s-switch-track::after { transform: translateX(13px); background: var(--h3s-accent); }
    .h3s-switch input:focus-visible + .h3s-switch-track { outline: 2px solid color-mix(in srgb, var(--h3s-accent) 70%, transparent); outline-offset: 1px; }
    .h3s-switch input:disabled + .h3s-switch-track, .h3s-switch input:disabled ~ .h3s-switch-label { opacity: .4; cursor: default; }
    .h3s-switch-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .h3s-megapixel-control { display: flex; flex-direction: column; gap: 4px; min-width: 0; padding: 1px 0; }
    .h3s-megapixel-top { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 5px; color: var(--h3s-muted); font-size: 8px; font-variant-numeric: tabular-nums; }
    .h3s-megapixel-top span:last-child { text-align: right; }
    .h3s-megapixel-value { min-width: 50px; color: var(--h3s-text); font-size: 10px; font-weight: 700; text-align: center; }
    .h3s-megapixel-control .h3s-range { height: 14px; margin: 0; }
    .h3s-megapixel-control .h3s-range-track::before { background: linear-gradient(90deg, #38d6af 0%, #68d391 18%, #e6ad55 48%, #ef7d52 72%, #ef5350 100%); }
    .h3s-megapixel-control .h3s-range[data-tier="experimental"] .h3s-range-thumb { background: #ef7d52; }
    .h3s-megapixel-control .h3s-range[data-tier="extreme"] .h3s-range-thumb { background: #ef5350; }
    .h3s-resolution-presets { display: flex; flex-wrap: wrap; gap: 3px; }
    .h3s-resolution-preset, .h3s-resolution-mode { min-height: 22px; padding: 3px 6px; border: 1px solid var(--h3s-border); border-radius: 5px; color: var(--h3s-muted); background: var(--h3s-bg); cursor: pointer; font: 620 8px/1.2 ui-sans-serif, system-ui; }
    .h3s-resolution-preset:hover, .h3s-resolution-mode:hover { color: var(--h3s-text); border-color: color-mix(in srgb, var(--h3s-accent) 45%, var(--h3s-border)); }
    .h3s-resolution-preset.is-active, .h3s-resolution-mode.is-active { color: var(--h3s-text); border-color: color-mix(in srgb, var(--h3s-accent) 65%, var(--h3s-border)); background: color-mix(in srgb, var(--h3s-accent) 12%, var(--h3s-bg)); }
    .h3s-resolution-modes { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; }
    .h3s-resolution-preview { display: grid; grid-template-columns: minmax(110px,.7fr) minmax(0,1.3fr); align-items: center; gap: 10px; min-height: 43px; padding: 7px 8px; border-radius: 6px; color: var(--h3s-muted); background: var(--h3s-bg); font-size: 9px; }
    .h3s-resolution-result, .h3s-resolution-status { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .h3s-resolution-result strong { color: var(--h3s-text); font-size: 12px; font-variant-numeric: tabular-nums; }
    .h3s-resolution-tier { width: fit-content; padding: 2px 5px; border-radius: 999px; color: #06120f; background: var(--h3s-accent); font-size: 8px; font-weight: 800; letter-spacing: .04em; }
    .h3s-resolution-tier.is-experimental { background: #ef9a57; }
    .h3s-resolution-tier.is-extreme { color: white; background: #d94a4a; }
    .h3s-resolution-note { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .h3s-reference-list { display: flex; flex-direction: column; gap: 6px; padding: 2px; border: 1px dashed transparent; border-radius: 7px; transition: border-color 120ms ease, background 120ms ease; }
    .h3s-reference-list.is-dragging { border-color: var(--h3s-accent); background: color-mix(in srgb, var(--h3s-accent) 8%, transparent); }
    .h3s-reference-card { display: grid; grid-template-columns: 64px minmax(0,1fr); align-items: start; gap: 7px; padding: 6px; border: 1px solid var(--h3s-border); border-radius: 6px; background: var(--h3s-bg); }
    .h3s-reference-card-auto { border-color: color-mix(in srgb, var(--h3s-accent) 45%, var(--h3s-border)); box-shadow: inset 2px 0 0 color-mix(in srgb, var(--h3s-accent) 75%, transparent); }
    .h3s-reference-thumb { --h3s-reference-ratio: 1; position: relative; width: 64px; aspect-ratio: var(--h3s-reference-ratio); overflow: hidden; border-radius: 5px; background: var(--h3s-raised); }
    .h3s-reference-thumb img { display: block; width: 100%; height: 100%; object-fit: contain; cursor: zoom-in; }
    .h3s-thumb-placeholder { display: grid; place-items: center; width: 100%; height: 100%; color: var(--h3s-muted); font-size: 9px; font-weight: 750; letter-spacing: .08em; }
    .h3s-reference-index { position: absolute; left: 4px; top: 4px; padding: 2px 4px; border-radius: 4px; color: #07120f; background: var(--h3s-accent); font-size: 9px; font-weight: 800; }
    .h3s-reference-body { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
    .h3s-reference-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
    .h3s-reference-name { overflow: hidden; color: var(--h3s-text); font-size: 10px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
    .h3s-reference-source { color: var(--h3s-muted); font-size: 8px; font-variant-numeric: tabular-nums; }
    .h3s-reference-actions { display: flex; flex: none; gap: 3px; }
    .h3s-icon-button { display: inline-grid; place-items: center; width: 23px; height: 23px; padding: 0; border: 1px solid var(--h3s-border); border-radius: 5px; color: var(--h3s-muted); background: var(--h3s-surface); cursor: pointer; font: 600 11px/1 ui-sans-serif, system-ui; }
    .h3s-icon-button:hover { color: var(--h3s-text); border-color: color-mix(in srgb, var(--h3s-accent) 35%, var(--h3s-border)); }
    .h3s-icon-button.h3s-danger:hover { color: #ff9a9a; border-color: color-mix(in srgb, #ff6b6b 45%, var(--h3s-border)); }
    .h3s-icon-button:disabled { cursor: default; opacity: .35; }
    .h3s-reference-controls { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; }
    .h3s-auto-role { width: fit-content; padding: 2px 6px; border-radius: 999px; color: var(--h3s-accent); background: color-mix(in srgb, var(--h3s-accent) 10%, transparent); font-size: 8px; font-weight: 650; }
    .h3s-reference-help { color: var(--h3s-muted); font-size: 8px; line-height: 1.35; }
    .h3s-reference-description { width: 100%; min-height: 38px; max-height: 74px; padding: 5px 7px; resize: vertical; border: 1px solid var(--h3s-border); border-radius: 6px; outline: none; color: var(--h3s-text); background: var(--h3s-surface); font: 10px/1.35 ui-sans-serif, system-ui; }
    .h3s-empty { display: flex; flex-direction: column; align-items: center; gap: 5px; padding: 14px 10px; border: 1px dashed var(--h3s-border); border-radius: 8px; color: var(--h3s-muted); text-align: center; }
    .h3s-empty strong { color: var(--h3s-text); font-size: 11px; }
    .h3s-empty span { max-width: 240px; font-size: 10px; }
    .h3s-result { padding: 0; border: 1px solid color-mix(in srgb, var(--h3s-accent) 24%, var(--h3s-border)); border-radius: 7px; background: color-mix(in srgb, var(--h3s-accent) 4%, var(--h3s-surface)); }
    .h3s-result summary { display: flex; align-items: center; justify-content: space-between; min-height: 29px; padding: 5px 8px; color: var(--h3s-text); cursor: pointer; font-size: 10px; font-weight: 680; list-style: none; }
    .h3s-result summary::-webkit-details-marker { display: none; }
    .h3s-copy-result { padding: 2px 7px; border: 1px solid var(--h3s-border); border-radius: 4px; color: var(--h3s-muted); background: transparent; cursor: pointer; font: 600 9px/1.4 ui-sans-serif, system-ui; }
    .h3s-copy-result:hover { color: var(--h3s-text); border-color: color-mix(in srgb, var(--h3s-accent) 40%, var(--h3s-border)); }
    .h3s-result-labels { display: flex; flex-wrap: wrap; gap: 4px; padding: 0 8px 6px; }
    .h3s-result-label { max-width: 100%; overflow: hidden; padding: 2px 5px; border-radius: 4px; color: var(--h3s-muted); background: var(--h3s-bg); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
    .h3s-result-prompt { max-height: 138px; margin: 0; padding: 8px; overflow: auto; border-top: 1px solid var(--h3s-border); color: var(--h3s-text); background: var(--h3s-bg); font: 9px/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; }
    .h3s-result-actions { display: flex; align-items: center; gap: 4px; }
    .h3s-prompt-studio { border: 1px solid var(--h3s-border); border-radius: 6px; background: var(--h3s-bg); }
    .h3s-prompt-studio > summary { padding: 6px 7px; color: var(--h3s-muted); cursor: pointer; font-size: 9px; font-weight: 650; }
    .h3s-prompt-studio > .h3s-section-stack { padding: 0 7px 7px; }
    .h3s-writer-instruction { box-sizing: border-box; width: 100%; min-height: 72px; resize: vertical; padding: 6px 7px; border: 1px solid var(--h3s-border); border-radius: 5px; outline: none; color: var(--h3s-text); background: var(--h3s-surface); font: 9px/1.45 ui-sans-serif, system-ui; }
    .h3s-writer-instruction:focus-visible { outline: 2px solid color-mix(in srgb, var(--h3s-accent) 70%, transparent); outline-offset: 1px; }
    .h3s-final-result { display: flex; flex-direction: column; gap: 6px; }
    .h3s-output-tabs { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 3px; padding: 3px; border: 1px solid var(--h3s-border); border-radius: 7px; background: var(--h3s-bg); }
    .h3s-output-tab { min-height: 25px; border: 0; border-radius: 5px; color: var(--h3s-muted); background: transparent; cursor: pointer; font: 650 9px/1.2 ui-sans-serif,system-ui; }
    .h3s-output-tab:hover { color: var(--h3s-text); }
    .h3s-output-tab.is-active { color: var(--h3s-text); background: color-mix(in srgb,var(--h3s-accent) 14%,var(--h3s-surface)); box-shadow: inset 0 0 0 1px color-mix(in srgb,var(--h3s-accent) 35%,transparent); }
    .h3s-output-stage { display: grid; place-items: center; min-height: 190px; overflow: hidden; border: 1px solid var(--h3s-border); border-radius: 8px; background: #090b0f; }
    .h3s-final-image { display: block; width: 100%; max-height: 430px; object-fit: contain; background: #090b0f; cursor: zoom-in; }
    .h3s-comparison-image { aspect-ratio: 8 / 5; }
    .h3s-final-metadata { padding: 0 2px; color: var(--h3s-muted); font-size: 9px; font-variant-numeric: tabular-nums; }
    .h3s-output-mode { padding: 2px 6px; border-radius: 999px; color: var(--h3s-accent); background: color-mix(in srgb,var(--h3s-accent) 10%,transparent); font-size: 8px; font-weight: 700; }
    .h3s-final-actions { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 5px; }
    .h3s-final-action { min-height: 27px; padding: 4px 6px; border: 1px solid var(--h3s-border); border-radius: 5px; color: var(--h3s-text); background: var(--h3s-bg); cursor: pointer; font: 650 9px/1.2 ui-sans-serif, system-ui; }
    .h3s-final-action:hover { border-color: color-mix(in srgb, var(--h3s-accent) 55%, var(--h3s-border)); background: color-mix(in srgb, var(--h3s-accent) 10%, var(--h3s-bg)); }
    .h3s-result-prompt .h3s-result-mention { display: inline-flex; max-width: 150px; margin: 0 2px; padding: 1px 5px 1px 3px; align-items: center; gap: 3px; border: 1px solid color-mix(in srgb, var(--h3s-accent) 55%, var(--h3s-border)); border-radius: 999px; color: var(--h3s-text); background: color-mix(in srgb, var(--h3s-accent) 14%, var(--h3s-surface)); font: 700 9px/1.45 ui-sans-serif, system-ui; vertical-align: 1px; white-space: nowrap; }
    .h3s-result-prompt .h3s-result-mention .h3s-mention-chip-thumb { width: 14px; height: 14px; margin: 0; border-radius: 3px; object-fit: cover; }
    .h3s-runtime-prompt { border-top: 1px solid var(--h3s-border); }
    .h3s-runtime-prompt > summary { min-height: 25px; padding-left: 8px; color: var(--h3s-muted); font-size: 9px; font-weight: 620; }
    .h3s-advanced-toggle { display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 0; border: 0; color: var(--h3s-muted); background: transparent; cursor: pointer; font: inherit; }
    .h3s-advanced-toggle:hover { color: var(--h3s-text); }
    .h3s-advanced-content[hidden] { display: none; }
    .h3s-warning { color: var(--h3s-warning); }
    .h3s-state-warning { padding: 7px 8px; border: 1px solid color-mix(in srgb, var(--h3s-warning) 45%, var(--h3s-border)); border-radius: 6px; color: var(--h3s-warning); background: color-mix(in srgb, var(--h3s-warning) 7%, var(--h3s-surface)); font-size: 9px; line-height: 1.45; }
    .h3s-live-preview { position: relative; display: grid; place-items: center; box-sizing: border-box; width: 100%; min-height: 0; max-height: 100%; height: 100%; overflow: hidden; border: 1px solid rgba(255,255,255,.13); border-radius: 8px; background: #111317; color: #9ca3af; font: 11px/1.4 ui-sans-serif, system-ui; }
    .h3s-live-preview-frame { position: absolute; inset: 0; display: block; width: 100%; height: 100%; object-fit: contain; object-position: center; opacity: 0; cursor: zoom-in; transition: opacity 110ms ease; pointer-events: none; }
    .h3s-live-preview-frame.is-visible { z-index: 1; opacity: 1; pointer-events: auto; }
    .h3s-live-preview-empty { max-width: 220px; padding: 18px; text-align: center; }
    .h3s-live-preview-status { position: absolute; z-index: 2; right: 7px; bottom: 7px; max-width: calc(100% - 100px); overflow: hidden; padding: 3px 7px; border-radius: 999px; background: rgba(0,0,0,.68); color: #e5e7eb; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
    .h3s-live-preview-navigation { position: absolute; z-index: 2; left: 7px; bottom: 7px; display: flex; align-items: center; gap: 4px; padding: 3px; border: 1px solid rgba(255,255,255,.12); border-radius: 999px; background: rgba(0,0,0,.72); backdrop-filter: blur(6px); }
    .h3s-live-preview-navigation[hidden] { display: none; }
    .h3s-live-preview-button { display: grid; place-items: center; width: 22px; height: 22px; padding: 0; border: 0; border-radius: 999px; color: #f3f4f6; background: rgba(255,255,255,.1); cursor: pointer; font: 18px/1 ui-sans-serif, system-ui; }
    .h3s-live-preview-button:hover:not(:disabled) { background: rgba(52,211,181,.28); }
    .h3s-live-preview-button:disabled { cursor: default; opacity: .3; }
    .h3s-live-preview-position { min-width: 32px; color: #e5e7eb; font-size: 9px; text-align: center; font-variant-numeric: tabular-nums; }
    .h3s-preview-lightbox { position: fixed; inset: 0; z-index: 100000; display: grid; place-items: center; padding: 28px; background: rgba(4,6,8,.91); backdrop-filter: blur(12px); cursor: zoom-out; }
    .h3s-preview-lightbox img { max-width: 96vw; max-height: 92vh; object-fit: contain; border-radius: 10px; box-shadow: 0 24px 80px rgba(0,0,0,.65); cursor: default; }
    .h3s-preview-lightbox-close { position: fixed; right: 22px; top: 18px; display: grid; place-items: center; width: 38px; height: 38px; padding: 0; border: 1px solid rgba(255,255,255,.18); border-radius: 999px; color: #f3f4f6; background: rgba(20,22,26,.8); cursor: pointer; font: 26px/1 ui-sans-serif, system-ui; }
    .h3s-preview-lightbox-close:hover { background: rgba(52,211,181,.22); }
    @media (max-width: 420px) {
      .h3s-grid, .h3s-reference-controls { grid-template-columns: 1fr; }
      .h3s-validation-notice { align-items: stretch; flex-direction: column; }
      .h3s-validation-fix { width: 100%; }
    }
  `;
  document.head.append(style);
}
