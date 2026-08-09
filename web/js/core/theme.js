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
    .h3s-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 6px; }
    .h3s-field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
    .h3s-field-label { color: var(--h3s-muted); font-size: 10px; font-weight: 600; }
    .h3s-field-hint { overflow: hidden; color: color-mix(in srgb, var(--h3s-muted) 75%, transparent); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
    .h3s-control { width: 100%; min-width: 0; height: 25px; padding: 3px 7px; border: 1px solid var(--h3s-border); border-radius: 5px; outline: none; color: var(--h3s-text); background: var(--h3s-bg); font: inherit; }
    .h3s-control:hover { border-color: color-mix(in srgb, var(--h3s-accent) 40%, var(--h3s-border)); }
    .h3s-control:focus-visible, .h3s-icon-button:focus-visible, .h3s-reference-description:focus-visible { outline: 2px solid color-mix(in srgb, var(--h3s-accent) 70%, transparent); outline-offset: 1px; }
    .h3s-seed-row { display: grid; grid-template-columns: minmax(0,1fr) 27px; gap: 4px; }
    .h3s-range { width: 100%; accent-color: var(--h3s-accent); }
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
    .h3s-megapixel-control { display: flex; flex-direction: column; gap: 2px; min-width: 0; padding: 1px 0; }
    .h3s-megapixel-top { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 5px; color: var(--h3s-muted); font-size: 8px; font-variant-numeric: tabular-nums; }
    .h3s-megapixel-top span:last-child { text-align: right; }
    .h3s-megapixel-value { min-width: 50px; color: var(--h3s-text); font-size: 10px; font-weight: 700; text-align: center; }
    .h3s-megapixel-control .h3s-range { height: 14px; margin: 0; cursor: pointer; }
    .h3s-resolution-preview { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 25px; padding: 5px 7px; border-radius: 6px; color: var(--h3s-muted); background: var(--h3s-bg); font-size: 10px; }
    .h3s-reference-list { display: flex; flex-direction: column; gap: 6px; padding: 2px; border: 1px dashed transparent; border-radius: 7px; transition: border-color 120ms ease, background 120ms ease; }
    .h3s-reference-list.is-dragging { border-color: var(--h3s-accent); background: color-mix(in srgb, var(--h3s-accent) 8%, transparent); }
    .h3s-reference-card { display: grid; grid-template-columns: 48px minmax(0,1fr); gap: 7px; padding: 6px; border: 1px solid var(--h3s-border); border-radius: 6px; background: var(--h3s-bg); }
    .h3s-reference-card-auto { border-color: color-mix(in srgb, var(--h3s-accent) 45%, var(--h3s-border)); box-shadow: inset 2px 0 0 color-mix(in srgb, var(--h3s-accent) 75%, transparent); }
    .h3s-reference-thumb { position: relative; width: 48px; height: 48px; overflow: hidden; border-radius: 5px; background: var(--h3s-raised); }
    .h3s-reference-thumb img { width: 100%; height: 100%; object-fit: cover; }
    .h3s-thumb-placeholder { display: grid; place-items: center; width: 100%; height: 100%; color: var(--h3s-muted); font-size: 9px; font-weight: 750; letter-spacing: .08em; }
    .h3s-reference-index { position: absolute; left: 4px; top: 4px; padding: 2px 4px; border-radius: 4px; color: #07120f; background: var(--h3s-accent); font-size: 9px; font-weight: 800; }
    .h3s-reference-body { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
    .h3s-reference-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
    .h3s-reference-name { overflow: hidden; color: var(--h3s-text); font-size: 10px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
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
    .h3s-runtime-prompt { border-top: 1px solid var(--h3s-border); }
    .h3s-runtime-prompt > summary { min-height: 25px; padding-left: 8px; color: var(--h3s-muted); font-size: 9px; font-weight: 620; }
    .h3s-advanced-toggle { display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 0; border: 0; color: var(--h3s-muted); background: transparent; cursor: pointer; font: inherit; }
    .h3s-advanced-toggle:hover { color: var(--h3s-text); }
    .h3s-advanced-content[hidden] { display: none; }
    .h3s-warning { color: var(--h3s-warning); }
    .h3s-live-preview { position: relative; display: grid; place-items: center; width: 100%; height: 220px; overflow: hidden; border: 1px solid rgba(255,255,255,.13); border-radius: 8px; background: #17191d; color: #9ca3af; font: 11px/1.4 ui-sans-serif, system-ui; }
    .h3s-live-preview img { width: 100%; height: 100%; object-fit: contain; cursor: zoom-in; }
    .h3s-live-preview img:not([src]) { display: none; }
    .h3s-live-preview-empty { max-width: 220px; padding: 18px; text-align: center; }
    .h3s-live-preview-status { position: absolute; right: 7px; bottom: 7px; padding: 3px 7px; border-radius: 999px; background: rgba(0,0,0,.68); color: #e5e7eb; font-size: 9px; }
    .h3s-live-preview-navigation { position: absolute; left: 7px; bottom: 7px; display: flex; align-items: center; gap: 4px; padding: 3px; border: 1px solid rgba(255,255,255,.12); border-radius: 999px; background: rgba(0,0,0,.72); backdrop-filter: blur(6px); }
    .h3s-live-preview-button { display: grid; place-items: center; width: 22px; height: 22px; padding: 0; border: 0; border-radius: 999px; color: #f3f4f6; background: rgba(255,255,255,.1); cursor: pointer; font: 18px/1 ui-sans-serif, system-ui; }
    .h3s-live-preview-button:hover:not(:disabled) { background: rgba(52,211,181,.28); }
    .h3s-live-preview-button:disabled { cursor: default; opacity: .3; }
    .h3s-live-preview-position { min-width: 32px; color: #e5e7eb; font-size: 9px; text-align: center; font-variant-numeric: tabular-nums; }
    .h3s-preview-lightbox { position: fixed; inset: 0; z-index: 100000; display: grid; place-items: center; padding: 28px; background: rgba(4,6,8,.91); backdrop-filter: blur(12px); cursor: zoom-out; }
    .h3s-preview-lightbox img { max-width: 96vw; max-height: 92vh; object-fit: contain; border-radius: 10px; box-shadow: 0 24px 80px rgba(0,0,0,.65); cursor: default; }
    .h3s-preview-lightbox-close { position: fixed; right: 22px; top: 18px; display: grid; place-items: center; width: 38px; height: 38px; padding: 0; border: 1px solid rgba(255,255,255,.18); border-radius: 999px; color: #f3f4f6; background: rgba(20,22,26,.8); cursor: pointer; font: 26px/1 ui-sans-serif, system-ui; }
    .h3s-preview-lightbox-close:hover { background: rgba(52,211,181,.22); }
    @media (max-width: 420px) { .h3s-grid, .h3s-reference-controls { grid-template-columns: 1fr; } }
  `;
  document.head.append(style);
}
