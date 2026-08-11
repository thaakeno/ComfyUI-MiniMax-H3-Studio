import { app } from "../../../scripts/app.js";

import { benchmarkMatrixSummary } from "./core/benchmark_matrix.js";

const TARGET = "H3StudioABComparison";

function widget(node, name) {
  return node.widgets?.find((candidate) => candidate.name === name);
}

function installCountPreview(node) {
  if (node.__h3studioBenchmarkCount || typeof node.addDOMWidget !== "function") return;
  node.__h3studioBenchmarkCount = true;
  const root = document.createElement("div");
  root.className = "h3s-benchmark-count";
  root.setAttribute("role", "status");
  root.setAttribute("aria-live", "polite");

  const render = () => {
    const summary = benchmarkMatrixSummary({
      comparisonKind: widget(node, "comparison_kind")?.value,
      profiles: widget(node, "profiles")?.value,
      megapixels: widget(node, "megapixels")?.value,
      repeats: widget(node, "repeats")?.value,
      maxGenerations: widget(node, "max_generations")?.value,
    });
    root.classList.toggle("is-warning", summary.guarded || !summary.valid);
    if (!summary.valid) {
      root.textContent = "Fix the profile or resolution list before running";
    } else if (summary.guarded) {
      root.textContent = `${summary.count} generations · above your safety guard · run will stop`;
    } else {
      root.textContent = `${summary.count} generations · ${summary.profileCount} profile${summary.profileCount === 1 ? "" : "s"} × ${summary.resolutionCount} resolution${summary.resolutionCount === 1 ? "" : "s"}`;
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
  display.computeSize = (width) => [width, 44];
  render();
}

app.registerExtension({
  name: "h3studio.benchmark-count",
  async setup() {
    if (document.getElementById("h3studio-benchmark-style")) return;
    const style = document.createElement("style");
    style.id = "h3studio-benchmark-style";
    style.textContent = `
      .h3s-benchmark-count { box-sizing: border-box; display: flex; align-items: center; min-height: 34px; margin: 4px 0; padding: 7px 9px; border: 1px solid color-mix(in srgb, #34d3b5 42%, transparent); border-radius: 6px; color: #b9f6e9; background: color-mix(in srgb, #34d3b5 10%, transparent); font: 650 11px/1.35 ui-sans-serif, system-ui; }
      .h3s-benchmark-count.is-warning { border-color: color-mix(in srgb, #f59e0b 55%, transparent); color: #ffd18a; background: color-mix(in srgb, #f59e0b 11%, transparent); }
    `;
    document.head.append(style);
  },
  async nodeCreated(node) {
    if (node.comfyClass === TARGET) installCountPreview(node);
  },
});
