import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const WORKFLOW_ID = "51ffc0bb-1b7a-4a1c-a183-1ce99edb4e5e";
const TARGET = "H3StudioModelSetup";
const DIRECTOR = "H3StudioDirector";
const NOTE = "H3StudioWorkflowNote";
const UAD_REPO = "https://github.com/thaakeno/comfyui-universal-asset-downloader.git";
const UAD_PAGE = "https://github.com/thaakeno/comfyui-universal-asset-downloader";

const ASSETS = [
  { id:"fl2va", group:"core", kind:"Diffusion", required:true, recommended:true, name:"FL2VA base · Kijai pruned W4A8", filename:"minimax_h3_fl2va_pruned_w4a8_mixed.safetensors", destination:"diffusion_models", url:"https://huggingface.co/Kijai/MiniMax-H3-experimental/resolve/main/minimax_h3_fl2va_pruned_w4a8_mixed.safetensors?download=true" },
  { id:"ref2va", group:"core", kind:"Diffusion", required:true, recommended:true, name:"REF2VA base · Kijai pruned W4A8", filename:"minimax_h3_ref2va_pruned_w4a8_mixed.safetensors", destination:"diffusion_models", url:"https://huggingface.co/Kijai/MiniMax-H3-experimental/resolve/main/minimax_h3_ref2va_pruned_w4a8_mixed.safetensors?download=true" },
  { id:"qwen32", group:"core", kind:"Text encoder", required:true, recommended:true, name:"H3 text encoder · Qwen3-VL 32B NVFP4", filename:"qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", destination:"text_encoders", url:"https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors?download=true" },
  { id:"vae", group:"core", kind:"VAE", required:true, recommended:true, name:"Final VAE · original H3 Video VAE FP16", filename:"minimax_h3_video_vae_fp16.safetensors", destination:"vae", url:"https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors?download=true" },
  { id:"qwen4", group:"core", kind:"Prompt writer", required:true, recommended:true, name:"Prompt analyzer / writer · Qwen3-VL 4B", filename:"qwen3vl_4b_fp8_scaled.safetensors", destination:"text_encoders", url:"https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors?download=true" },

  { id:"lx8pruned", group:"accel-recommended", kind:"LoRA", required:false, recommended:true, name:"FL2VA · LightX v1.0 · 8-step · Kijai pruned rank-24", filename:"minimax_h3_fl2v_lightx2v_turbo_8step_v1.0_resized_avg_rank_24_bf16.safetensors", destination:"loras", url:"https://huggingface.co/Kijai/MiniMax-H3_comfy/resolve/main/loras/minimax_h3_fl2v_lightx2v_turbo_8step_v1.0_resized_avg_rank_24_bf16.safetensors?download=true" },
  { id:"lx4v1", group:"accel-recommended", kind:"LoRA", required:false, recommended:false, name:"FL2VA · LightX v1.0 · 4-step 768p · Kijai pruned rank-31", filename:"minimax_h3_fl2v_lightx2v_turbo_4step_v1.0_768p_resized_avg_rank_31_bf16.safetensors", destination:"loras", url:"https://huggingface.co/Kijai/MiniMax-H3_comfy/resolve/main/loras/minimax_h3_fl2v_lightx2v_turbo_4step_v1.0_768p_resized_avg_rank_31_bf16.safetensors?download=true" },

  { id:"lx8full", group:"accel-alternative", kind:"LoRA", required:false, recommended:false, name:"FL2VA · LightX v1.0 · 8-step · official full", filename:"minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", destination:"loras", url:"https://huggingface.co/lightx2v/Minimax-h3-Turbo/resolve/main/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors?download=true" },
  { id:"lx4v01", group:"accel-alternative", kind:"LoRA", required:false, recommended:false, name:"FL2VA · LightX v0.1 · 4-step · Kijai rank-21", filename:"minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors", destination:"loras", url:"https://huggingface.co/Kijai/MiniMax-H3_comfy/resolve/main/loras/minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors?download=true" },
  { id:"ref4", group:"accel-alternative", kind:"LoRA", required:false, recommended:false, name:"REF2VA · LightX v0.1 · 4-step · Kijai rank-20", filename:"minimax_h3_ref2v_lightx2v_turbo_4step_v0.1_resized_avg_rank_20_bf16.safetensors", destination:"loras", url:"https://huggingface.co/Kijai/MiniMax-H3_comfy/resolve/main/loras/minimax_h3_ref2v_lightx2v_turbo_4step_v0.1_resized_avg_rank_20_bf16.safetensors?download=true" },

  { id:"taeh3", group:"extras", kind:"Preview VAE", required:false, recommended:true, name:"TAEH3 live preview", filename:"taeh3.safetensors", destination:"vae_approx", url:"https://huggingface.co/Kijai/MiniMax-H3-TAE/resolve/main/vae_approx/taeh3.safetensors?download=true" },
  { id:"t1vae500k", group:"extras", kind:"Experimental VAE", required:false, recommended:false, name:"Single-frame Image VAE 500K · Comfy", filename:"minimax_h3_single_frame_500k_comfy.safetensors", destination:"vae", url:"https://huggingface.co/Alissonerdx/MiniMax-H3-Single-Frame-VAE-500K-Comfy/resolve/main/minimax_h3_single_frame_500k_comfy.safetensors?download=true" },
  { id:"t1vae", group:"extras", kind:"Experimental VAE", required:false, recommended:false, name:"Legacy T=1 Image VAE · Mamad8", filename:"minimax_h3_t1_image_vae_step1597.safetensors", destination:"vae", url:"https://huggingface.co/Mamad8/MiniMax-H3-Image-VAE/resolve/main/minimax_h3_t1_image_vae_step1597.safetensors?download=true" },
  { id:"qwen8", group:"extras", kind:"Prompt writer", required:false, recommended:false, name:"Optional Qwen3-VL 8B writer", filename:"qwen3vl_8b_fp8_scaled.safetensors", destination:"text_encoders", url:"https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_8b_fp8_scaled.safetensors?download=true" },
];

const GROUPS = [
  { key:"core", title:"Core runtime", subtitle:"Required H3 bases, encoders and final VAE. No acceleration LoRAs live here.", tone:"core" },
  { key:"accel-recommended", title:"Acceleration · recommended", subtitle:"Optional LightX LoRAs. The 8-step rank-24 profile is the default fast path.", tone:"recommended" },
  { key:"accel-alternative", title:"Acceleration · alternatives", subtitle:"Other LightX recipes. Install only the profile you intend to use.", tone:"alternative" },
  { key:"extras", title:"Preview & optional extras", subtitle:"Preview VAE and alternate writer/VAE components. Not required for the core runtime.", tone:"extras" },
];

function className(node) { return String(node?.comfyClass || node?.type || ""); }
function bytesLabel(bytes) {
  let value = Number(bytes) || 0;
  if (!value) return "size pending";
  const units = ["B","KB","MB","GB","TB"];
  let unit = units[0];
  for (const candidate of units) { unit = candidate; if (value < 1024 || candidate === "TB") break; value /= 1024; }
  return `${value.toFixed(unit === "GB" || unit === "TB" ? 2 : 1)} ${unit}`;
}
function maintained(graphData) {
  const nodes = graphData?.nodes || [];
  return String(graphData?.id || "") === WORKFLOW_ID || (nodes.some(n => String(n?.type || "") === DIRECTOR) && nodes.some(n=>Number(n?.id)===28 && String(n?.type||"")===NOTE));
}
function ensureSerializedSetup(graphData) {
  if (!maintained(graphData)) return;
  const nodes = graphData.nodes || (graphData.nodes = []);
  let node = nodes.find(n => String(n?.type || "") === TARGET);
  if (!node) {
    const id = Math.max(Number(graphData.last_node_id) || 0, ...nodes.map(n => Number(n?.id) || 0)) + 1;
    node = { id, type:TARGET, pos:[-2380,220], size:[820,860], flags:{}, order:0, mode:0, inputs:[], outputs:[], title:"Model setup · verify & install", properties:{"Node name for S&R":TARGET}, widgets_values:[] };
    nodes.push(node);
    graphData.last_node_id = id;
  }
}

async function jsonFetch(path, options = {}) {
  const response = await fetch(path, options);
  let data = null;
  try { data = await response.json(); } catch { data = null; }
  if (!response.ok || data?.ok === false) throw Object.assign(new Error(data?.error || `HTTP ${response.status}`), { status: response.status });
  return data;
}
async function postJson(path, payload) {
  return jsonFetch(path, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) });
}

function injectStyles() {
  if (document.getElementById("h3-model-setup-style")) return;
  const style = document.createElement("style");
  style.id = "h3-model-setup-style";
  style.textContent = `
    .h3ms{box-sizing:border-box;width:100%;height:100%;overflow:auto;padding:12px;color:#e8eeef;background:linear-gradient(180deg,#111918,#0e1514);font:11px/1.45 ui-sans-serif,system-ui;border:1px solid rgba(255,255,255,.11);border-radius:9px}.h3ms *{box-sizing:border-box}
    .h3ms-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;position:sticky;top:-12px;z-index:3;padding:12px 0 9px;background:linear-gradient(180deg,#111918 82%,rgba(17,25,24,0))}.h3ms-title{font-size:16px;font-weight:800}.h3ms-sub{opacity:.62;margin-top:2px;max-width:500px}.h3ms-badge{white-space:nowrap;padding:5px 8px;border:1px solid rgba(255,255,255,.12);border-radius:999px;background:rgba(255,255,255,.04)}.h3ms-badge.ok{border-color:rgba(52,211,153,.42);color:#a7f3d0}.h3ms-badge.warn{border-color:rgba(245,158,11,.45);color:#fde68a}
    .h3ms-card{margin-top:8px;padding:10px;border:1px solid rgba(255,255,255,.1);border-radius:9px;background:rgba(255,255,255,.025)}.h3ms-actions{display:flex;gap:6px;flex-wrap:wrap;align-items:center}.h3ms-btn{padding:7px 9px;border:1px solid rgba(255,255,255,.13);border-radius:7px;background:rgba(255,255,255,.07);color:inherit;cursor:pointer;font-weight:680;text-decoration:none}.h3ms-btn:hover{background:rgba(255,255,255,.12)}.h3ms-btn:disabled{opacity:.38;cursor:not-allowed}.h3ms-primary{border-color:rgba(45,212,191,.42);background:rgba(45,212,191,.13)}
    .h3ms-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px}.h3ms-stat{padding:7px;border:1px solid rgba(255,255,255,.08);border-radius:7px;background:rgba(0,0,0,.12)}.h3ms-stat small{display:block;opacity:.5;text-transform:uppercase;font-size:8px;letter-spacing:.07em}.h3ms-stat strong{display:block;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .h3ms-group{margin-top:10px;padding:8px;border:1px solid rgba(255,255,255,.085);border-radius:9px;background:rgba(255,255,255,.018)}.h3ms-group.core{border-color:rgba(56,189,248,.20)}.h3ms-group.recommended{border-color:rgba(45,212,191,.25)}.h3ms-group.alternative{border-color:rgba(167,139,250,.20)}.h3ms-group.extras{border-color:rgba(251,191,36,.16)}
    .h3ms-group-head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;padding:1px 2px 7px}.h3ms-group-title{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.065em;color:#d7f6f0}.h3ms-group-sub{font-size:9px;opacity:.54;margin-top:2px}.h3ms-group-count{font-size:9px;opacity:.55;white-space:nowrap}
    .h3ms-row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:8px;padding:7px 5px;border-top:1px solid rgba(255,255,255,.052);align-items:start}.h3ms-name{color:#e4fbf7;text-decoration:none;font-weight:680}.h3ms-name:hover{text-decoration:underline}.h3ms-meta{display:flex;gap:4px;flex-wrap:wrap;margin-top:3px}.h3ms-chip{padding:1px 5px;border:1px solid rgba(255,255,255,.1);border-radius:999px;font-size:8px;opacity:.76}.h3ms-chip.lora{border-color:rgba(167,139,250,.3);color:#ddd6fe}.h3ms-chip.required{border-color:rgba(56,189,248,.28);color:#bae6fd}.h3ms-chip.recommended{border-color:rgba(45,212,191,.28);color:#99f6e4}.h3ms-path{margin-top:4px;opacity:.52;font:8.5px/1.35 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}.h3ms-status{min-width:76px;text-align:right;font-size:9px}.h3ms-status.ok{color:#86efac}.h3ms-status.bad{color:#fca5a5}.h3ms-status.wait{opacity:.52}.h3ms-hf{width:13px;height:13px;vertical-align:-2px;margin-right:4px;border-radius:2px}
    .h3ms-log{margin-top:8px;padding:8px;border:1px solid rgba(255,255,255,.08);border-radius:7px;background:#0a1110;white-space:pre-wrap;overflow-wrap:anywhere;min-height:34px;max-height:90px;overflow:auto}.h3ms-progress{height:4px;background:rgba(255,255,255,.08);border-radius:99px;overflow:hidden;margin-top:6px}.h3ms-progress>div{height:100%;width:0;background:#64d8c2;transition:width .12s}.h3ms-missing{font-size:11px}.h3ms-missing a{color:#7dd3fc}.h3ms-note{opacity:.66;margin-top:6px}.h3ms-footer{margin-top:9px;padding-top:7px;border-top:1px solid rgba(255,255,255,.08);opacity:.68}.h3ms-footer a{color:#7dd3fc}
  `;
  document.head.append(style);
}

function predictedPath(state, asset) {
  const relative = `models/${asset.destination}/${asset.filename}`;
  return state.modelsDir ? `${String(state.modelsDir).replace(/[\\/]$/, "")}/${asset.destination}/${asset.filename}` : relative;
}

const MODEL_SETUP_NODE_CHROME = 54;
const MODEL_SETUP_MIN_VIEWPORT = 320;
const MODEL_SETUP_MIN_WIDTH = 480;
const MODEL_SETUP_DEFAULT_NODE_WIDTH = 820;
const MODEL_SETUP_DEFAULT_NODE_HEIGHT = 860;

function modelSetupViewportHeight(nodeHeight) {
  const height = Number(nodeHeight);
  const resolved = Number.isFinite(height) && height > 0 ? height : MODEL_SETUP_DEFAULT_NODE_HEIGHT;
  return Math.max(MODEL_SETUP_MIN_VIEWPORT, Math.round(resolved) - MODEL_SETUP_NODE_CHROME);
}

function modelSetupWidgetSizing(node) {
  const height = () => modelSetupViewportHeight(node?.size?.[1]);
  return {
    getMinHeight: height,
    getMaxHeight: height,
    getHeight: height,
  };
}

function installUI(node) {
  if (node.__h3ModelSetup || typeof node.addDOMWidget !== "function") return;
  injectStyles();
  const root = document.createElement("div");
  root.className = "h3ms";
  const state = {
    uad:null,
    manager:false,
    managerHasUad:false,
    metadata:new Map(),
    verification:new Map(),
    selected:new Set(ASSETS.filter(a=>a.recommended).map(a=>a.id)),
    busy:false,
    metadataLoading:false,
    metadataPromise:null,
    modelsDir:"",
    progress:0,
  };
  node.__h3ModelSetup = { root, state };

  const setLog = (text) => { const el=root.querySelector('[data-log]'); if(el) el.textContent=text; };
  const setProgress = (value) => {
    state.progress=Math.max(0,Math.min(100,Number(value)||0));
    const el=root.querySelector('.h3ms-progress>div'); if(el) el.style.width=`${state.progress}%`;
  };
  const setBusy = (busy) => {
    state.busy=busy;
    root.querySelectorAll('button[data-blocking="1"]').forEach(button=>button.disabled=busy);
  };

  const updateSelectedStats = () => {
    const selected = ASSETS.filter(a=>state.selected.has(a.id));
    const selectedBytes = selected.reduce((sum,a)=>sum+(Number(state.metadata.get(a.id)?.size_bytes)||0),0);
    const el = root.querySelector('[data-stat="selected"]');
    if (el) el.textContent = `${selected.length} · ${bytesLabel(selectedBytes)}`;
  };

  const render = () => {
    const prevScrollTop = Number(root.scrollTop || 0);
    const prevScrollLeft = Number(root.scrollLeft || 0);
    const selected = ASSETS.filter(a=>state.selected.has(a.id));
    const selectedBytes = selected.reduce((sum,a)=>sum+(Number(state.metadata.get(a.id)?.size_bytes)||0),0);
    const knownBytes = ASSETS.reduce((sum,a)=>sum+(Number(state.metadata.get(a.id)?.size_bytes)||0),0);
    const verifiedCount = [...state.verification.values()].filter(v=>v?.ok).length;
    const missingCount = [...state.verification.values()].filter(v=>v?.status==='missing').length;
    const uadReady = Boolean(state.uad?.capabilities?.install);
    let body = `<div class="h3ms-head"><div><div class="h3ms-title">H3 Studio · Model Setup</div><div class="h3ms-sub">Required runtime models are separated from acceleration LoRAs. Verify exact paths, inspect sizes and install only what you need.</div></div><div class="h3ms-badge ${uadReady?'ok':'warn'}">${uadReady?`UAD ${state.uad.version||''} connected`:'UAD required'}</div></div>`;

    if (!uadReady) {
      const old = state.managerHasUad
        ? `<b>Universal Asset Downloader is installed, but this integration needs the current UAD v2.</b><div class="h3ms-note">Update UAD in ComfyUI-Manager, restart ComfyUI, then press R or hard refresh this page.</div>`
        : `<b>Universal Asset Downloader is not loaded.</b><div class="h3ms-note">It stays a separate package so H3 Studio and the downloader can update independently. Direct Hugging Face links and exact model directories are listed below for manual installation.</div>`;
      body += `<div class="h3ms-card h3ms-missing">${old}<div class="h3ms-actions" style="margin-top:9px">${state.manager&&!state.managerHasUad?'<button class="h3ms-btn h3ms-primary" data-action="install-uad" data-blocking="1">Install UAD with Manager</button>':''}<a class="h3ms-btn" href="${UAD_PAGE}" target="_blank" rel="noopener noreferrer">Open UAD repo ↗</a><button class="h3ms-btn" data-action="recheck" data-blocking="1">Recheck</button></div>${state.manager?'':'<div class="h3ms-note">ComfyUI-Manager was not detected, so automatic installation is unavailable.</div>'}</div>`;
    }

    body += `<div class="h3ms-actions"><button class="h3ms-btn" data-action="required">Select required</button><button class="h3ms-btn" data-action="recommended">Select recommended setup</button><button class="h3ms-btn" data-action="metadata" data-blocking="1" ${uadReady?'':'disabled title="Requires Universal Asset Downloader"'}>${state.metadataLoading?'Loading sizes…':'Refresh sizes'}</button><button class="h3ms-btn" data-action="verify" data-blocking="1" ${uadReady?'':'disabled title="Requires Universal Asset Downloader"'}>Verify all</button><button class="h3ms-btn h3ms-primary" data-action="download" data-blocking="1" ${uadReady?'':'disabled title="Requires Universal Asset Downloader"'}>Download selected missing</button><button class="h3ms-btn" data-action="repair" data-blocking="1" ${uadReady?'':'disabled title="Requires Universal Asset Downloader"'}>Repair selected</button></div>`;
    body += `<div class="h3ms-stats"><div class="h3ms-stat"><small>Selected</small><strong data-stat="selected">${selected.length} · ${bytesLabel(selectedBytes)}</strong></div><div class="h3ms-stat"><small>Known total</small><strong>${bytesLabel(knownBytes)}</strong></div><div class="h3ms-stat"><small>Verified</small><strong>${verifiedCount}/${ASSETS.length}</strong></div><div class="h3ms-stat"><small>Missing</small><strong>${state.verification.size?missingCount:'not checked'}</strong></div></div>`;

    for (const group of GROUPS) {
      const groupAssets=ASSETS.filter(asset=>asset.group===group.key);
      body += `<section class="h3ms-group ${group.tone}"><div class="h3ms-group-head"><div><div class="h3ms-group-title">${group.title}</div><div class="h3ms-group-sub">${group.subtitle}</div></div><div class="h3ms-group-count">${groupAssets.length} file${groupAssets.length===1?'':'s'}</div></div>`;
      for (const asset of groupAssets) {
        const meta = state.metadata.get(asset.id) || {};
        const check = state.verification.get(asset.id);
        const status = !check ? ['wait','not checked'] : check.ok ? ['ok','verified'] : check.status==='missing' ? ['wait','missing'] : ['bad',check.status||'attention'];
        const path = check?.path || predictedPath(state,asset);
        const roleChip = asset.kind === 'LoRA' ? '<span class="h3ms-chip lora">LoRA</span>' : `<span class="h3ms-chip">${asset.kind}</span>`;
        body += `<div class="h3ms-row"><input type="checkbox" data-select="${asset.id}" ${state.selected.has(asset.id)?'checked':''}><div><a class="h3ms-name" href="${asset.url}" target="_blank" rel="noopener noreferrer"><img class="h3ms-hf" src="https://huggingface.co/favicon.ico">${asset.name} ↗</a><div class="h3ms-meta"><span class="h3ms-chip">${meta.size_label||bytesLabel(meta.size_bytes)}</span>${roleChip}<span class="h3ms-chip">models/${asset.destination}</span>${asset.required?'<span class="h3ms-chip required">required</span>':''}${asset.recommended&&!asset.required?'<span class="h3ms-chip recommended">recommended</span>':''}</div><div class="h3ms-path">${path}</div></div><div class="h3ms-status ${status[0]}">${status[1]}</div></div>`;
      }
      body += `</section>`;
    }

    body += `<div class="h3ms-card"><b>PDD · optional REF2VA acceleration</b><div class="h3ms-note">PDD is separate from the LightX LoRA groups above and uses its own LoRA + heads pair.</div><div style="margin-top:5px"><a href="https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8" target="_blank" rel="noopener noreferrer" style="color:#7dd3fc">Open MiniMax H3 PDD ↗</a></div></div>`;
    body += `<div class="h3ms-log" data-log>${!uadReady ? 'UAD is not connected. Install UAD for automatic atomic downloads and verification, or download models manually from the links above.' : state.metadataLoading ? 'Loading provider sizes and hashes in background workers. The rest of ComfyUI remains usable.' : 'Ready. Verify checks exact paths; downloads use UAD atomic install + provider verification.'}</div><div class="h3ms-progress"><div style="width:${state.progress}%"></div></div><div class="h3ms-footer">Downloader integration: <a href="${UAD_PAGE}" target="_blank" rel="noopener noreferrer">Universal Asset Downloader ↗</a></div>`;
    root.innerHTML = body;
    bind();
    setBusy(state.busy);
    root.scrollTop = prevScrollTop;
    root.scrollLeft = prevScrollLeft;
    queueMicrotask(() => {
      if (root.isConnected) {
        root.scrollTop = prevScrollTop;
        root.scrollLeft = prevScrollLeft;
      }
    });
  };

  async function detect() {
    state.uad=null;
    state.manager=false;
    state.managerHasUad=false;
    try {
      const status=await jsonFetch('/uad/status');
      state.uad=status;
      state.modelsDir=status.models_dir||'';
    } catch {}
    try {
      const response=await fetch('/customnode/installed?mode=default');
      if(response.ok){
        state.manager=true;
        const data=await response.json();
        state.managerHasUad=JSON.stringify(data).toLowerCase().includes('comfyui-universal-asset-downloader');
      }
    } catch {}
    render();
    if(state.uad?.capabilities?.analyze && !state.metadata.size) ensureMetadata(false);
  }

  async function installUad() {
    if(!state.manager) return;
    if(!window.confirm('Install Universal Asset Downloader from thaakeno/comfyui-universal-asset-downloader using ComfyUI-Manager?')) return;
    setBusy(true);
    setLog('Asking ComfyUI-Manager to install UAD…');
    try {
      const response=await fetch('/customnode/install/git_url',{method:'POST',headers:{'Content-Type':'text/plain'},body:UAD_REPO});
      const text=await response.text();
      if(!response.ok) throw Object.assign(new Error(text||`HTTP ${response.status}`),{status:response.status});
      setLog('UAD installed. Restart ComfyUI, then press R or hard refresh the browser so the backend routes and UI load.');
    } catch(error) {
      setLog(error.status===403 ? 'Manager blocked automatic installation because of its security policy. Install/update UAD through Manager manually.' : `UAD installation failed: ${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function ensureMetadata(showLog=true) {
    if(!state.uad) return;
    if(state.metadataPromise) return state.metadataPromise;
    state.metadataLoading=true;
    if(showLog) setLog('Loading exact sizes and provider hashes in background workers…');
    render();

    const queue=[...ASSETS];
    let done=0;
    const worker=async()=>{
      while(queue.length){
        const asset=queue.shift();
        try {
          const result=await postJson('/uad/analyze-fast',{url:asset.url});
          const found=(result.assets||[]).find(item=>item.filename===asset.filename)||(result.assets||[])[0];
          if(found) state.metadata.set(asset.id,{...found,id:asset.id,destination:asset.destination,filename:asset.filename,source_url:asset.url});
        } catch(error) {
          state.metadata.set(asset.id,{id:asset.id,destination:asset.destination,filename:asset.filename,source_url:asset.url,error:error.message});
        }
        done+=1;
        setProgress(done/ASSETS.length*100);
      }
    };

    state.metadataPromise=(async()=>{
      await Promise.all(Array.from({length:Math.min(4,ASSETS.length)},()=>worker()));
      state.metadataLoading=false;
      state.metadataPromise=null;
      setProgress(0);
      render();
      if(showLog) setLog('Sizes and provider hashes refreshed.');
    })();
    return state.metadataPromise;
  }

  function installItems(ids) {
    return ids.map(id => {
      const asset=ASSETS.find(a=>a.id===id);
      const meta=state.metadata.get(id)||{};
      return {...meta,id,provider:meta.provider||'huggingface',filename:asset.filename,destination:asset.destination,download_url:meta.download_url||asset.url,source_url:asset.url};
    });
  }

  async function verifyAll() {
    await ensureMetadata(false);
    setBusy(true);
    setLog(`Verifying ${ASSETS.length} exact model paths in a worker thread…`);
    try {
      const result=await postJson('/uad/verify-fast',{items:installItems(ASSETS.map(a=>a.id))});
      (result.results||[]).forEach((item,index)=>state.verification.set(ASSETS[index].id,item));
      const good=[...state.verification.values()].filter(v=>v.ok).length;
      render();
      setLog(`${good}/${ASSETS.length} verified. Missing entries show the exact path where UAD will save them.`);
      return result.results||[];
    } catch(error) {
      setLog(`Verification failed: ${error.message}`);
      return [];
    } finally {
      setBusy(false);
    }
  }

  async function downloadSelected(repair=false) {
    await ensureMetadata(false);
    if(!state.verification.size) await verifyAll();
    const ids=[...state.selected];
    const targets=ids.filter(id=>{
      const verification=state.verification.get(id);
      return repair ? !verification?.ok : verification?.status==='missing';
    });
    if(!targets.length){
      setLog(repair?'Selected files are already verified.':'No selected files are missing.');
      return;
    }
    if(repair && !window.confirm(`Repair/redownload ${targets.length} selected file(s) that failed verification? Existing bad files are replaced only after a successful verified download.`)) return;
    setBusy(true);
    setLog(`${repair?'Repairing':'Downloading'} ${targets.length} model file(s)…`);
    setProgress(0);
    try {
      await postJson('/uad/install',{items:installItems(targets),node_id:String(node.id),force:repair});
      setLog('Install finished. Re-verifying exact paths…');
    } catch(error) {
      setLog(`Install failed: ${error.message}`);
    } finally {
      setBusy(false);
      setProgress(0);
      await verifyAll();
    }
  }

  function selectBy(predicate) {
    state.selected=new Set(ASSETS.filter(predicate).map(asset=>asset.id));
    root.querySelectorAll('[data-select]').forEach(input=>{
      input.checked=state.selected.has(input.dataset.select);
    });
    updateSelectedStats();
  }

  function bind() {
    root.querySelectorAll('[data-select]').forEach(input=>input.addEventListener('change',()=>{
      input.checked?state.selected.add(input.dataset.select):state.selected.delete(input.dataset.select);
      updateSelectedStats();
    }));
    root.querySelector('[data-action="recheck"]')?.addEventListener('click',detect);
    root.querySelector('[data-action="install-uad"]')?.addEventListener('click',installUad);
    root.querySelector('[data-action="required"]')?.addEventListener('click',()=>selectBy(asset=>asset.required));
    root.querySelector('[data-action="recommended"]')?.addEventListener('click',()=>selectBy(asset=>asset.recommended));
    root.querySelector('[data-action="metadata"]')?.addEventListener('click',()=>ensureMetadata(true));
    root.querySelector('[data-action="verify"]')?.addEventListener('click',verifyAll);
    root.querySelector('[data-action="download"]')?.addEventListener('click',()=>downloadSelected(false));
    root.querySelector('[data-action="repair"]')?.addEventListener('click',()=>downloadSelected(true));
  }

  node.computeSize = function h3ModelSetupComputeSize() {
    return [MODEL_SETUP_MIN_WIDTH, MODEL_SETUP_MIN_VIEWPORT + MODEL_SETUP_NODE_CHROME];
  };

  const widget = node.addDOMWidget("h3_model_setup", "h3_model_setup", root, {
    serialize: false,
    hideOnZoom: false,
    getValue: () => undefined,
    ...modelSetupWidgetSizing(node),
  });
  widget.computeSize = (width) => [
    Math.max(MODEL_SETUP_MIN_WIDTH, Number(width) || MODEL_SETUP_DEFAULT_NODE_WIDTH),
    modelSetupViewportHeight(node.size?.[1]),
  ];
  node.setSize?.([
    Math.max(node.size?.[0] || MODEL_SETUP_DEFAULT_NODE_WIDTH, MODEL_SETUP_MIN_WIDTH),
    Math.max(node.size?.[1] || MODEL_SETUP_DEFAULT_NODE_HEIGHT, MODEL_SETUP_MIN_VIEWPORT + MODEL_SETUP_NODE_CHROME),
  ]);

  const originalOnResize = node.onResize;
  node.onResize = function h3ModelSetupOnResize(size) {
    originalOnResize?.apply(this, arguments);
    if (root && size) {
      const height = modelSetupViewportHeight(size[1]);
      root.style.height = `${height}px`;
      const wrapper = root.parentElement;
      if (wrapper) {
        wrapper.style.height = `${height}px`;
        wrapper.style.width = `${Math.max(MODEL_SETUP_MIN_WIDTH, size[0] - 20)}px`;
      }
    }
  };
  render();
  detect();
}

function patchDownloadNote() {
  const note=app.graph?.getNodeById?.(28);
  if(className(note)!==NOTE) return;
  const text=note.widgets?.find(w=>w.name==='text');
  if(!text || typeof text.value!=='string') return;
  const old='> **Install manually:** place each file in the shown `ComfyUI/models/` folder. H3 Studio never downloads model weights automatically. Acceleration profiles load the exact matching LoRA by filename, so do **not** add these profile LoRAs again as custom LoRAs.';
  const next='> **Recommended:** use **H3 Studio · Model Setup** on the left. Core runtime models and acceleration LoRAs are separated there, with exact paths, sizes, verification and safe UAD downloads. The links below remain the manual fallback.';
  if(text.value.includes(old)){
    text.value=text.value.replace(old,next);
    text.callback?.(text.value,app.canvas,note,[0,0],{});
  }
}

api.addEventListener('uad-progress',({detail})=>{
  const node=app.graph?.getNodeById?.(Number(detail?.node))||app.graph?.getNodeById?.(detail?.node);
  const setup=node?.__h3ModelSetup;
  if(!setup) return;
  const progress=Number(detail?.progress);
  if(Number.isFinite(progress)) setup.state.progress=Math.max(0,Math.min(100,progress));
  const log=setup.root.querySelector('[data-log]');
  if(log&&detail?.status) log.textContent=detail.status;
  const bar=setup.root.querySelector('.h3ms-progress>div');
  if(bar&&Number.isFinite(progress)) bar.style.width=`${setup.state.progress}%`;
});

app.registerExtension({
  name:'H3Studio.ModelSetup',
  beforeConfigureGraph(graphData){ ensureSerializedSetup(graphData); },
  afterConfigureGraph(){ setTimeout(patchDownloadNote,0); },
  async nodeCreated(node){ if(className(node)===TARGET) installUI(node); },
});