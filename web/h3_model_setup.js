import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const WORKFLOW_ID = "51ffc0bb-1b7a-4a1c-a183-1ce99edb4e5e";
const TARGET = "H3StudioModelSetup";
const DIRECTOR = "H3StudioDirector";
const NOTE = "H3StudioWorkflowNote";
const UAD_REPO = "https://github.com/thaakeno/comfyui-universal-asset-downloader.git";
const UAD_PAGE = "https://github.com/thaakeno/comfyui-universal-asset-downloader";

const ASSETS = [
  { id:"fl2va", group:"Core models", name:"FL2VA base · Kijai pruned W4A8", filename:"minimax_h3_fl2va_pruned_w4a8_mixed.safetensors", destination:"diffusion_models", recommended:true, url:"https://huggingface.co/Kijai/MiniMax-H3-experimental/resolve/main/minimax_h3_fl2va_pruned_w4a8_mixed.safetensors?download=true" },
  { id:"ref2va", group:"Core models", name:"REF2VA base · Kijai pruned W4A8", filename:"minimax_h3_ref2va_pruned_w4a8_mixed.safetensors", destination:"diffusion_models", recommended:true, url:"https://huggingface.co/Kijai/MiniMax-H3-experimental/resolve/main/minimax_h3_ref2va_pruned_w4a8_mixed.safetensors?download=true" },
  { id:"qwen32", group:"Core models", name:"H3 text encoder · Qwen3-VL 32B NVFP4", filename:"qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", destination:"text_encoders", recommended:true, url:"https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors?download=true" },
  { id:"vae", group:"Core models", name:"Final VAE · original H3 Video VAE FP16", filename:"minimax_h3_video_vae_fp16.safetensors", destination:"vae", recommended:true, url:"https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors?download=true" },
  { id:"qwen4", group:"Core models", name:"Prompt analyzer / writer · Qwen3-VL 4B", filename:"qwen3vl_4b_fp8_scaled.safetensors", destination:"text_encoders", recommended:true, url:"https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors?download=true" },

  { id:"lx8pruned", group:"Recommended acceleration", name:"FL2VA · LightX v1.0 · 8-step · Kijai pruned rank-24", filename:"minimax_h3_fl2v_lightx2v_turbo_8step_v1.0_resized_avg_rank_24_bf16.safetensors", destination:"loras", recommended:true, url:"https://huggingface.co/Kijai/MiniMax-H3_comfy/resolve/main/loras/minimax_h3_fl2v_lightx2v_turbo_8step_v1.0_resized_avg_rank_24_bf16.safetensors?download=true" },
  { id:"lx4v1", group:"Recommended acceleration", name:"FL2VA · LightX v1.0 · 4-step 768p · Kijai pruned rank-31", filename:"minimax_h3_fl2v_lightx2v_turbo_4step_v1.0_768p_resized_avg_rank_31_bf16.safetensors", destination:"loras", recommended:false, url:"https://huggingface.co/Kijai/MiniMax-H3_comfy/resolve/main/loras/minimax_h3_fl2v_lightx2v_turbo_4step_v1.0_768p_resized_avg_rank_31_bf16.safetensors?download=true" },
  { id:"lx8full", group:"Alternative acceleration", name:"FL2VA · LightX v1.0 · 8-step · official full", filename:"minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", destination:"loras", recommended:false, url:"https://huggingface.co/lightx2v/Minimax-h3-Turbo/resolve/main/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors?download=true" },
  { id:"lx4v01", group:"Alternative acceleration", name:"FL2VA · LightX v0.1 · 4-step · Kijai rank-21", filename:"minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors", destination:"loras", recommended:false, url:"https://huggingface.co/Kijai/MiniMax-H3_comfy/resolve/main/loras/minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors?download=true" },
  { id:"ref4", group:"Alternative acceleration", name:"REF2VA · LightX v0.1 · 4-step · Kijai rank-20", filename:"minimax_h3_ref2v_lightx2v_turbo_4step_v0.1_resized_avg_rank_20_bf16.safetensors", destination:"loras", recommended:false, url:"https://huggingface.co/Kijai/MiniMax-H3_comfy/resolve/main/loras/minimax_h3_ref2v_lightx2v_turbo_4step_v0.1_resized_avg_rank_20_bf16.safetensors?download=true" },

  { id:"taeh3", group:"Preview / VAE extras", name:"TAEH3 live preview", filename:"taeh3.safetensors", destination:"vae_approx", recommended:true, url:"https://huggingface.co/Kijai/MiniMax-H3-TAE/resolve/main/vae_approx/taeh3.safetensors?download=true" },
  { id:"t1vae", group:"Preview / VAE extras", name:"Experimental T=1 Image VAE", filename:"minimax_h3_t1_image_vae_step1597.safetensors", destination:"vae", recommended:false, url:"https://huggingface.co/Mamad8/MiniMax-H3-Image-VAE/resolve/main/minimax_h3_t1_image_vae_step1597.safetensors?download=true" },
  { id:"qwen8", group:"Preview / VAE extras", name:"Optional Qwen3-VL 8B writer", filename:"qwen3vl_8b_fp8_scaled.safetensors", destination:"text_encoders", recommended:false, url:"https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_8b_fp8_scaled.safetensors?download=true" },
];

const GROUPS = ["Core models", "Recommended acceleration", "Alternative acceleration", "Preview / VAE extras"];

function className(node) { return String(node?.comfyClass || node?.type || ""); }
function bytesLabel(bytes) {
  let value = Number(bytes) || 0;
  if (!value) return "size unknown";
  const units = ["B","KB","MB","GB","TB"];
  let unit = units[0];
  for (const candidate of units) { unit = candidate; if (value < 1024 || candidate === "TB") break; value /= 1024; }
  return `${value.toFixed(unit === "GB" || unit === "TB" ? 2 : 1)} ${unit}`;
}
function maintained(graphData) {
  const nodes = graphData?.nodes || [];
  return String(graphData?.id || "") === WORKFLOW_ID || (nodes.some(n => String(n?.type || "") === DIRECTOR) && nodes.some(n => Number(n?.id) === 28 && String(n?.type || "") === NOTE));
}
function ensureSerializedSetup(graphData) {
  if (!maintained(graphData)) return;
  const nodes = graphData.nodes || (graphData.nodes = []);
  let node = nodes.find(n => String(n?.type || "") === TARGET);
  if (!node) {
    const id = Math.max(Number(graphData.last_node_id) || 0, ...nodes.map(n => Number(n?.id) || 0)) + 1;
    node = { id, type:TARGET, pos:[-2350,220], size:[780,900], flags:{}, order:0, mode:0, inputs:[], outputs:[], title:"Model setup · verify & install", properties:{"Node name for S&R":TARGET}, widgets_values:[] };
    nodes.push(node);
    graphData.last_node_id = id;
  }
  node.pos = [-2350,220];
  node.size = [780,900];
  node.title = "Model setup · verify & install";
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
    .h3ms{box-sizing:border-box;width:100%;height:100%;overflow:auto;padding:12px;color:#e7ecef;background:#111817;font:11px/1.45 ui-sans-serif,system-ui;border:1px solid rgba(255,255,255,.11);border-radius:9px}.h3ms *{box-sizing:border-box}
    .h3ms-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.h3ms-title{font-size:16px;font-weight:780}.h3ms-sub{opacity:.62;margin-top:2px}.h3ms-badge{white-space:nowrap;padding:5px 8px;border:1px solid rgba(255,255,255,.12);border-radius:999px;background:rgba(255,255,255,.04)}.h3ms-badge.ok{border-color:rgba(52,211,153,.42);color:#a7f3d0}.h3ms-badge.warn{border-color:rgba(245,158,11,.45);color:#fde68a}
    .h3ms-card{margin-top:10px;padding:10px;border:1px solid rgba(255,255,255,.1);border-radius:8px;background:rgba(255,255,255,.025)}.h3ms-actions{display:flex;gap:6px;flex-wrap:wrap;align-items:center}.h3ms-btn{padding:7px 9px;border:1px solid rgba(255,255,255,.13);border-radius:7px;background:rgba(255,255,255,.07);color:inherit;cursor:pointer;font-weight:650}.h3ms-btn:hover{background:rgba(255,255,255,.12)}.h3ms-btn:disabled{opacity:.38;cursor:not-allowed}.h3ms-primary{border-color:rgba(45,212,191,.42);background:rgba(45,212,191,.13)}
    .h3ms-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:9px}.h3ms-stat{padding:7px;border:1px solid rgba(255,255,255,.08);border-radius:7px}.h3ms-stat small{display:block;opacity:.55;text-transform:uppercase;font-size:8px;letter-spacing:.07em}.h3ms-stat strong{display:block;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .h3ms-group{margin-top:11px}.h3ms-group-title{font-size:10px;font-weight:760;text-transform:uppercase;letter-spacing:.06em;color:#7de3d0;margin-bottom:5px}.h3ms-row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:7px;padding:7px 5px;border-top:1px solid rgba(255,255,255,.055);align-items:start}.h3ms-name{color:#dffaf5;text-decoration:none;font-weight:650}.h3ms-name:hover{text-decoration:underline}.h3ms-meta{display:flex;gap:4px;flex-wrap:wrap;margin-top:3px}.h3ms-chip{padding:1px 5px;border:1px solid rgba(255,255,255,.1);border-radius:999px;font-size:9px;opacity:.78}.h3ms-path{margin-top:4px;opacity:.58;font:9px/1.35 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}.h3ms-status{min-width:72px;text-align:right;font-size:9px}.h3ms-status.ok{color:#86efac}.h3ms-status.bad{color:#fca5a5}.h3ms-status.wait{opacity:.55}.h3ms-hf{width:14px;height:14px;vertical-align:-3px;margin-right:4px;border-radius:2px}
    .h3ms-log{margin-top:9px;padding:8px;border:1px solid rgba(255,255,255,.08);border-radius:7px;background:#0b1110;white-space:pre-wrap;overflow-wrap:anywhere;min-height:36px}.h3ms-progress{height:5px;background:rgba(255,255,255,.08);border-radius:99px;overflow:hidden;margin-top:7px}.h3ms-progress>div{height:100%;width:0;background:#64d8c2;transition:width .15s}.h3ms-missing{font-size:12px}.h3ms-missing a{color:#7dd3fc}.h3ms-note{opacity:.7;margin-top:6px}.h3ms-footer{margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,.08);opacity:.72}.h3ms-footer a{color:#7dd3fc}
  `;
  document.head.append(style);
}

function predictedPath(state, asset) {
  const relative = `models/${asset.destination}/${asset.filename}`;
  return state.modelsDir ? `${String(state.modelsDir).replace(/[\\/]$/, "")}/${asset.destination}/${asset.filename}` : relative;
}

function installUI(node) {
  if (node.__h3ModelSetup || typeof node.addDOMWidget !== "function") return;
  injectStyles();
  const root = document.createElement("div"); root.className = "h3ms";
  const state = { uad:null, manager:false, managerHasUad:false, metadata:new Map(), verification:new Map(), selected:new Set(ASSETS.filter(a=>a.recommended).map(a=>a.id)), busy:false, modelsDir:"", progress:0 };
  node.__h3ModelSetup = { root, state };

  const render = () => {
    const selected = ASSETS.filter(a=>state.selected.has(a.id));
    const selectedBytes = selected.reduce((sum,a)=>sum+(Number(state.metadata.get(a.id)?.size_bytes)||0),0);
    const knownBytes = ASSETS.reduce((sum,a)=>sum+(Number(state.metadata.get(a.id)?.size_bytes)||0),0);
    const verifiedCount = [...state.verification.values()].filter(v=>v?.ok).length;
    const uadReady = Boolean(state.uad?.capabilities?.install);
    let body = `<div class="h3ms-head"><div><div class="h3ms-title">H3 Studio · Model Setup</div><div class="h3ms-sub">One place to inspect, verify and install the maintained H3 model set.</div></div><div class="h3ms-badge ${uadReady?'ok':'warn'}">${uadReady?`UAD ${state.uad.version||''} connected`:'UAD required'}</div></div>`;

    if (!uadReady) {
      const old = state.managerHasUad ? `<b>Universal Asset Downloader is installed, but this H3 integration needs UAD v2.</b><div class="h3ms-note">Update UAD in ComfyUI-Manager, restart ComfyUI, then press R or hard refresh this page.</div>` : `<b>Universal Asset Downloader is not loaded.</b><div class="h3ms-note">H3 Studio keeps downloading separate so both nodes remain independently updateable.</div>`;
      body += `<div class="h3ms-card h3ms-missing">${old}<div class="h3ms-actions" style="margin-top:9px">${state.manager&&!state.managerHasUad?'<button class="h3ms-btn h3ms-primary" data-action="install-uad">Install UAD with Manager</button>':''}<a class="h3ms-btn" href="${UAD_PAGE}" target="_blank" rel="noopener noreferrer">Open UAD repo ↗</a><button class="h3ms-btn" data-action="recheck">Recheck</button></div>${state.manager?'':'<div class="h3ms-note">ComfyUI-Manager was not detected, so automatic custom-node installation is unavailable.</div>'}</div>`;
      body += `<div class="h3ms-log" data-log>${state.managerHasUad?'Waiting for UAD v2 after update + restart.':'Install UAD, restart ComfyUI, then reload the browser.'}</div>`;
      root.innerHTML = body; bind(); return;
    }

    body += `<div class="h3ms-actions" style="margin-top:10px"><button class="h3ms-btn" data-action="recommended">Select recommended</button><button class="h3ms-btn" data-action="metadata">Refresh metadata</button><button class="h3ms-btn" data-action="verify">Verify all</button><button class="h3ms-btn h3ms-primary" data-action="download">Download selected missing</button><button class="h3ms-btn" data-action="repair">Repair selected</button></div>`;
    body += `<div class="h3ms-stats"><div class="h3ms-stat"><small>Selected</small><strong>${selected.length} · ${bytesLabel(selectedBytes)}</strong></div><div class="h3ms-stat"><small>Known model set</small><strong>${bytesLabel(knownBytes)}</strong></div><div class="h3ms-stat"><small>Verified</small><strong>${verifiedCount}/${ASSETS.length}</strong></div></div>`;

    for (const group of GROUPS) {
      body += `<div class="h3ms-group"><div class="h3ms-group-title">${group}</div>`;
      for (const asset of ASSETS.filter(a=>a.group===group)) {
        const meta = state.metadata.get(asset.id) || {};
        const check = state.verification.get(asset.id);
        const status = !check ? ['wait','not checked'] : check.ok ? ['ok','verified'] : check.status==='missing' ? ['wait','missing'] : ['bad',check.status||'attention'];
        const path = check?.path || predictedPath(state,asset);
        body += `<div class="h3ms-row"><input type="checkbox" data-select="${asset.id}" ${state.selected.has(asset.id)?'checked':''}><div><a class="h3ms-name" href="${asset.url}" target="_blank" rel="noopener noreferrer"><img class="h3ms-hf" src="https://huggingface.co/favicon.ico">${asset.name} ↗</a><div class="h3ms-meta"><span class="h3ms-chip">${meta.size_label||bytesLabel(meta.size_bytes)}</span><span class="h3ms-chip">${asset.destination}</span>${asset.recommended?'<span class="h3ms-chip">recommended</span>':''}</div><div class="h3ms-path">${path}</div></div><div class="h3ms-status ${status[0]}">${status[1]}</div></div>`;
      }
      body += `</div>`;
    }
    body += `<div class="h3ms-card"><b>PDD · optional REF2VA acceleration</b><div class="h3ms-note">PDD is a separate custom node and uses its own LoRA + heads pair.</div><div style="margin-top:5px"><a href="https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8" target="_blank" rel="noopener noreferrer" style="color:#7dd3fc">Open MiniMax H3 PDD ↗</a></div></div>`;
    body += `<div class="h3ms-log" data-log>Ready. Verify checks the exact expected path; downloads use UAD's safe atomic installer and provider verification.</div><div class="h3ms-progress"><div style="width:${state.progress}%"></div></div><div class="h3ms-footer">UAD stays a separate node package. <a href="${UAD_PAGE}" target="_blank" rel="noopener noreferrer">Universal Asset Downloader ↗</a></div>`;
    root.innerHTML = body; bind();
  };

  const setLog = (text) => { const el=root.querySelector('[data-log]'); if(el) el.textContent=text; };
  const setBusy = (busy) => { state.busy=busy; root.querySelectorAll('button').forEach(b=>b.disabled=busy); };

  async function detect() {
    state.uad=null; state.manager=false; state.managerHasUad=false;
    try { const status=await jsonFetch('/uad/status'); state.uad=status; state.modelsDir=status.models_dir||''; } catch {}
    try {
      const response=await fetch('/customnode/installed?mode=default');
      if(response.ok){ state.manager=true; const data=await response.json(); state.managerHasUad=JSON.stringify(data).toLowerCase().includes('comfyui-universal-asset-downloader'); }
    } catch {}
    render();
    if(state.uad?.capabilities?.analyze && !state.metadata.size) refreshMetadata(false);
  }

  async function installUad() {
    if(!state.manager) return;
    if(!window.confirm('Install Universal Asset Downloader from thaakeno/comfyui-universal-asset-downloader using ComfyUI-Manager?')) return;
    setBusy(true); setLog('Asking ComfyUI-Manager to install UAD…');
    try {
      const response=await fetch('/customnode/install/git_url',{method:'POST',headers:{'Content-Type':'text/plain'},body:UAD_REPO});
      const text=await response.text();
      if(!response.ok) throw Object.assign(new Error(text||`HTTP ${response.status}`),{status:response.status});
      setLog('UAD installed. Restart ComfyUI, then press R or hard refresh the browser so the new backend routes and node UI load.');
    } catch(error) {
      setLog(error.status===403 ? 'Manager blocked automatic installation because of its security policy. Open the UAD repo and install/update it through Manager manually.' : `UAD installation failed: ${error.message}`);
    } finally { setBusy(false); }
  }

  async function refreshMetadata(showLog=true) {
    if(!state.uad) return;
    setBusy(true); if(showLog)setLog('Reading Hugging Face metadata for exact file sizes and hashes…');
    let done=0;
    for(const asset of ASSETS){
      try {
        const result=await postJson('/uad/analyze',{url:asset.url});
        const found=(result.assets||[]).find(item=>item.filename===asset.filename)||(result.assets||[])[0];
        if(found) state.metadata.set(asset.id,{...found,id:asset.id,destination:asset.destination,filename:asset.filename,source_url:asset.url});
      } catch(error) { state.metadata.set(asset.id,{id:asset.id,destination:asset.destination,filename:asset.filename,source_url:asset.url,error:error.message}); }
      done++; state.progress=done/ASSETS.length*100; render();
    }
    state.progress=0; render(); if(showLog)setLog('Metadata refreshed. Sizes and provider hashes are ready for verification.'); setBusy(false);
  }

  function installItems(ids) {
    return ids.map(id => {
      const asset=ASSETS.find(a=>a.id===id); const meta=state.metadata.get(id)||{};
      return {...meta,id,provider:meta.provider||'huggingface',filename:asset.filename,destination:asset.destination,download_url:meta.download_url||asset.url,source_url:asset.url};
    });
  }

  async function verifyAll() {
    if(state.metadata.size<ASSETS.length) await refreshMetadata(false);
    setBusy(true); setLog(`Verifying ${ASSETS.length} exact model paths…`);
    try {
      const result=await postJson('/uad/verify',{items:installItems(ASSETS.map(a=>a.id))});
      (result.results||[]).forEach((item,index)=>state.verification.set(ASSETS[index].id,item));
      const good=[...state.verification.values()].filter(v=>v.ok).length; render(); setLog(`${good}/${ASSETS.length} verified. Missing files show the exact path where UAD will save them.`);
      return result.results||[];
    } catch(error){ setLog(`Verification failed: ${error.message}`); return []; }
    finally { setBusy(false); }
  }

  async function downloadSelected(repair=false) {
    if(state.metadata.size<ASSETS.length) await refreshMetadata(false);
    if(!state.verification.size) await verifyAll();
    const ids=[...state.selected];
    const targets=ids.filter(id=>{ const v=state.verification.get(id); return repair ? !v?.ok : v?.status==='missing'; });
    if(!targets.length){ setLog(repair?'Selected files are already verified.':'No selected files are missing.'); return; }
    if(repair && !window.confirm(`Repair/redownload ${targets.length} selected file(s) that failed verification? Existing bad files will be replaced only after a successful verified download.`)) return;
    setBusy(true); setLog(`${repair?'Repairing':'Downloading'} ${targets.length} model file(s)…`); state.progress=0; render();
    try {
      await postJson('/uad/install',{items:installItems(targets),node_id:String(node.id),force:repair});
      setLog('Install finished. Re-verifying exact paths…');
    } catch(error){ setLog(`Install failed: ${error.message}`); }
    finally { setBusy(false); state.progress=0; await verifyAll(); }
  }

  function bind() {
    root.querySelectorAll('[data-select]').forEach(input=>input.addEventListener('change',()=>{ input.checked?state.selected.add(input.dataset.select):state.selected.delete(input.dataset.select); render(); }));
    root.querySelector('[data-action="recheck"]')?.addEventListener('click',detect);
    root.querySelector('[data-action="install-uad"]')?.addEventListener('click',installUad);
    root.querySelector('[data-action="recommended"]')?.addEventListener('click',()=>{state.selected=new Set(ASSETS.filter(a=>a.recommended).map(a=>a.id));render();});
    root.querySelector('[data-action="metadata"]')?.addEventListener('click',()=>refreshMetadata(true));
    root.querySelector('[data-action="verify"]')?.addEventListener('click',verifyAll);
    root.querySelector('[data-action="download"]')?.addEventListener('click',()=>downloadSelected(false));
    root.querySelector('[data-action="repair"]')?.addEventListener('click',()=>downloadSelected(true));
  }

  const widget=node.addDOMWidget('h3_model_setup','h3_model_setup',root,{serialize:false,hideOnZoom:false});
  widget.computeSize=(width)=>[width,Math.max(820,(node.size?.[1]||900)-30)];
  node.setSize?.([Math.max(node.size?.[0]||780,780),Math.max(node.size?.[1]||900,900)]);
  render(); detect();
}

function patchDownloadNote() {
  const note=app.graph?.getNodeById?.(28);
  if(className(note)!==NOTE) return;
  const text=note.widgets?.find(w=>w.name==='text');
  if(!text || typeof text.value!=='string') return;
  const old='> **Install manually:** place each file in the shown `ComfyUI/models/` folder. H3 Studio never downloads model weights automatically. Acceleration profiles load the exact matching LoRA by filename, so do **not** add these profile LoRAs again as custom LoRAs.';
  const next='> **Recommended:** use **H3 Studio · Model Setup** on the left to verify exact paths and download missing files through Universal Asset Downloader. The links below remain the manual fallback. Acceleration profiles load the exact matching LoRA by filename, so do **not** add these profile LoRAs again as custom LoRAs.';
  if(text.value.includes(old)){ text.value=text.value.replace(old,next); text.callback?.(text.value,app.canvas,note,[0,0],{}); }
}

api.addEventListener('uad-progress',({detail})=>{
  const node=app.graph?.getNodeById?.(Number(detail?.node))||app.graph?.getNodeById?.(detail?.node);
  const setup=node?.__h3ModelSetup; if(!setup) return;
  const progress=Number(detail?.progress); if(Number.isFinite(progress)) setup.state.progress=Math.max(0,Math.min(100,progress));
  const log=setup.root.querySelector('[data-log]'); if(log&&detail?.status) log.textContent=detail.status;
  const bar=setup.root.querySelector('.h3ms-progress>div'); if(bar&&Number.isFinite(progress)) bar.style.width=`${setup.state.progress}%`;
});

app.registerExtension({
  name:'H3Studio.ModelSetup',
  beforeConfigureGraph(graphData){ ensureSerializedSetup(graphData); },
  afterConfigureGraph(){ setTimeout(patchDownloadNote,0); },
  async nodeCreated(node){ if(className(node)===TARGET) installUI(node); },
});
