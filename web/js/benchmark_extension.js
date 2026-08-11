import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

import { benchmarkMatrixSummary } from "./core/benchmark_matrix.js";
import { openImageLightbox } from "./core/lightbox.js";

const TARGET = "H3StudioABComparison";

function widget(node, name) {
  return node.widgets?.find((candidate) => candidate.name === name);
}

function installCountPreview(node) {
  if (node.__h3studioBenchmarkCount || typeof node.addDOMWidget !== "function") return;
  node.__h3studioBenchmarkCount = true;
  const root = document.createElement("div");
  root.className = "h3s-benchmark-panel";
  root.setAttribute("role", "status");
  root.setAttribute("aria-live", "polite");
  const count = document.createElement("div");
  count.className = "h3s-benchmark-count";
  const progress = document.createElement("div");
  progress.className = "h3s-benchmark-progress";
  progress.hidden = true;
  const bar = document.createElement("div");
  bar.className = "h3s-benchmark-bar";
  const fill = document.createElement("div");
  fill.className = "h3s-benchmark-bar-fill";
  bar.append(fill);
  const active = document.createElement("div");
  active.className = "h3s-benchmark-active";
  const timing = document.createElement("div");
  timing.className = "h3s-benchmark-timing";
  const previews = document.createElement("div");
  previews.className = "h3s-benchmark-previews";
  progress.append(bar, active, timing, previews);
  root.append(count, progress);

  const render = () => {
    const summary = benchmarkMatrixSummary({
      comparisonKind: widget(node, "comparison_kind")?.value,
      profiles: widget(node, "profiles")?.value,
      megapixels: widget(node, "megapixels")?.value,
      repeats: widget(node, "repeats")?.value,
      maxGenerations: widget(node, "max_generations")?.value,
    });
    count.classList.toggle("is-warning", summary.guarded || !summary.valid);
    if (!summary.valid) {
      count.textContent = "Fix the profile or resolution list before running";
    } else if (summary.guarded) {
      count.textContent = `${summary.count} generations · above your safety guard · run will stop`;
    } else {
      count.textContent = `${summary.count} generations · ${summary.profileCount} profile${summary.profileCount === 1 ? "" : "s"} × ${summary.resolutionCount} resolution${summary.resolutionCount === 1 ? "" : "s"}`;
    }
  };

  for (const name of ["comparison_kind", "profiles", "megapixels", "repeats", "max_generations"]) {
    const target = widget(node, name);
    if (!target || target.__h3studioBenchmarkCallback) continue;
    const previous = target.callback;
    target.callback = function (...args) {
      const result = previous?.apply(this, args);
      render();
      return result;
    };
    target.__h3studioBenchmarkCallback = true;
  }

  const display = node.addDOMWidget("h3studio_benchmark_count", "h3studio_benchmark_count", root, {
    serialize: false,
    hideOnZoom: false,
  });
  display.computeSize = (width) => [width, progress.hidden ? 44 : Math.min(260, 104 + previews.childElementCount * 8)];
  node.__h3studioBenchmarkProgress = { progress, fill, active, timing, previews, display };
  render();
}

function seconds(value) {
  const total = Math.max(0, Number(value) || 0);
  if (total < 60) return `${total.toFixed(1)}s`;
  return `${Math.floor(total / 60)}m ${Math.round(total % 60)}s`;
}

api.addEventListener("h3studio-benchmark-progress", ({ detail }) => {
  const node = app.graph?.getNodeById?.(Number(detail?.node_id));
  const elements = node?.__h3studioBenchmarkProgress;
  if (!elements) return;
  const total = Math.max(1, Number(detail.total) || 1);
  const finished = Math.max(0, Number(detail.finished) || 0);
  elements.progress.hidden = false;
  elements.fill.style.width = `${Math.min(100, (finished / total) * 100)}%`;
  if (detail.phase === "preparing") {
    elements.previews.replaceChildren();
    elements.active.textContent = `Preparing benchmark · 0/${total}`;
  } else {
    const canvas = detail.width && detail.height ? ` · ${detail.width}×${detail.height}` : "";
    elements.active.textContent = `${detail.phase === "complete" ? "Finished" : `Running ${detail.current}/${total}`} · ${detail.profile || "benchmark"}${canvas}`;
  }
  const eta = detail.eta_seconds != null ? ` · ETA ≈ ${seconds(detail.eta_seconds)}` : "";
  elements.timing.textContent = `${finished} finished · ${detail.remaining ?? total - finished} remaining · ${seconds(detail.elapsed_seconds)} elapsed${eta}`;
  if (detail.preview) {
    const image = document.createElement("img");
    image.src = detail.preview;
    image.alt = `${detail.profile || "Benchmark"} ${detail.width || ""}×${detail.height || ""}`;
    image.title = `${detail.profile || "Benchmark"} · ${detail.requested_megapixels} MP · seed ${detail.seed}`;
    image.addEventListener("click", () => openImageLightbox(image.src, image.title));
    elements.previews.append(image);
  }
  elements.display.computeSize = (width) => [width, elements.previews.childElementCount ? 210 : 112];
  node.setDirtyCanvas?.(true, true);
});

app.registerExtension({
  name: "h3studio.benchmark-count",
  async setup() {
    if (document.getElementById("h3studio-benchmark-style")) return;
    const style = document.createElement("style");
    style.id = "h3studio-benchmark-style";
    style.textContent = `
      .h3s-benchmark-panel { box-sizing: border-box; display: flex; flex-direction: column; gap: 7px; width: 100%; padding: 4px 0; font: 650 11px/1.35 ui-sans-serif, system-ui; }
      .h3s-benchmark-count { box-sizing: border-box; display: flex; align-items: center; min-height: 34px; padding: 7px 9px; border: 1px solid color-mix(in srgb, #34d3b5 42%, transparent); border-radius: 6px; color: #b9f6e9; background: color-mix(in srgb, #34d3b5 10%, transparent); }
      .h3s-benchmark-count.is-warning { border-color: color-mix(in srgb, #f59e0b 55%, transparent); color: #ffd18a; background: color-mix(in srgb, #f59e0b 11%, transparent); }
      .h3s-benchmark-progress { display: flex; flex-direction: column; gap: 5px; padding: 7px 9px; border-radius: 6px; color: #dbe3ec; background: color-mix(in srgb, #111827 82%, transparent); }
      .h3s-benchmark-progress[hidden] { display: none; }
      .h3s-benchmark-bar { height: 5px; overflow: hidden; border-radius: 999px; background: rgba(255,255,255,.12); }
      .h3s-benchmark-bar-fill { width: 0; height: 100%; border-radius: inherit; background: #34d3b5; transition: width 180ms ease; }
      .h3s-benchmark-active { overflow: hidden; color: #f3f4f6; text-overflow: ellipsis; white-space: nowrap; }
      .h3s-benchmark-timing { color: #9ca3af; font-size: 10px; font-weight: 500; }
      .h3s-benchmark-previews { display: flex; gap: 5px; overflow-x: auto; }
      .h3s-benchmark-previews:empty { display: none; }
      .h3s-benchmark-previews img { width: 72px; height: 72px; flex: none; object-fit: contain; border: 1px solid rgba(255,255,255,.12); border-radius: 4px; background: #080b10; cursor: zoom-in; }
    `;
    document.head.append(style);
  },
  async nodeCreated(node) {
    if (node.comfyClass === TARGET) installCountPreview(node);
  },
});
