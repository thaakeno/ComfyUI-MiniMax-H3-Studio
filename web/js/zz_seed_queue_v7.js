import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

import {
  normalizeState,
  releaseSeedQueueReservation,
  reserveSeedAfterQueue,
  restorePersistedState,
  serializeState,
} from "./core/state.js";
import { isNodeDownstream } from "./core/final_output.js";

const TARGET = "H3StudioDirector";
const STATE_PROPERTY = "h3studio_state";
const FINAL_OUTPUTS = new Set(["PreviewImage", "H3StudioSaveImage", "H3StudioComparisonView"]);
const installedNodes = new Set();
const actualSeedByPrompt = new Map();
let activePromptId = "";

function widget(node, name) {
  return node?.widgets?.find((candidate) => candidate.name === name) || null;
}

function promptId(detail) {
  return String(detail?.prompt_id || detail?.promptId || activePromptId || "");
}

function outputValue(message, key) {
  const value = message?.[key];
  if (Array.isArray(value)) return value[0];
  return value;
}

function randomSeed() {
  const values = new Uint32Array(2);
  globalThis.crypto?.getRandomValues?.(values);
  const combined = values[0] * 0x200000 + (values[1] & 0x1fffff);
  return combined || Math.floor(Math.random() * Number.MAX_SAFE_INTEGER);
}

function readState(node) {
  const restored = restorePersistedState(
    widget(node, "studio_state")?.value,
    node?.properties?.[STATE_PROPERTY],
  );
  const state = normalizeState(restored.state);
  const nativeSeed = Number(widget(node, "seed")?.value);
  if (Number.isFinite(nativeSeed) && nativeSeed >= 0) {
    state.generation.seed = Math.trunc(nativeSeed);
  }
  return state;
}

function syncVisibleSeed(node, seed) {
  const control = node?.__h3studioPanel?.querySelector?.('input[aria-label="Seed"]');
  if (control) control.value = String(seed);
}

function writeState(node, state) {
  const normalized = normalizeState(state);
  const serialized = serializeState(normalized);
  const seedWidget = widget(node, "seed");
  const stateWidget = widget(node, "studio_state");
  if (seedWidget) seedWidget.value = normalized.generation.seed;
  if (stateWidget) stateWidget.value = serialized;
  node.properties ||= {};
  node.properties[STATE_PROPERTY] = serialized;
  node.__h3studioState = normalized;
  syncVisibleSeed(node, normalized.generation.seed);
  node.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
  globalThis.dispatchEvent?.(new CustomEvent("h3studio:seed-reserved", {
    detail: {
      nodeId: Number(node.id),
      seed: normalized.generation.seed,
      pending: normalized.generation.seed_queue_reservations,
    },
  }));
}

function reserveNextSeed(node) {
  const state = readState(node);
  if (state.generation.seed_locked) return;
  state.generation = reserveSeedAfterQueue(state.generation, randomSeed);
  writeState(node, state);
}

function releaseFailedReservation(node) {
  const state = readState(node);
  if (state.generation.seed_queue_reservations <= 0) return;
  state.generation = releaseSeedQueueReservation(state.generation);
  writeState(node, state);
}

function captureActualSeed(node, message) {
  const seed = Number(outputValue(message, "seed"));
  const id = activePromptId;
  if (!id || !Number.isFinite(seed) || seed < 0) return;
  actualSeedByPrompt.set(id, { nodeId: String(node.id), seed: Math.trunc(seed) });
}

function installQueueSeed(node) {
  if (!node || installedNodes.has(node.id) || node.__h3studioQueueSeedV7Installed) return;
  const seedWidget = widget(node, "seed");
  if (!seedWidget) return;

  node.__h3studioQueueSeedV7Installed = true;
  installedNodes.add(node.id);

  const originalAfterQueued = seedWidget.afterQueued;
  seedWidget.afterQueued = function h3studioSeedAfterQueued(options) {
    const result = originalAfterQueued?.apply(this, arguments);
    // ComfyUI serializes graphToPrompt(), POSTs it to /prompt, and only then
    // runs widget afterQueued callbacks before serializing the next queued Run.
    // That gives every rapidly queued prompt a unique immutable seed without
    // mutating the payload that was just accepted by the server.
    reserveNextSeed(node);
    return result;
  };

  // The backend Director returns the exact seed that belonged to this execution.
  // Queue-time reservation means the visible UI is already showing the *next*
  // seed by then, so retain the executed seed by prompt id for final-image
  // metadata and "same seed" reruns.
  const originalExecuted = node.onExecuted;
  node.onExecuted = function h3studioQueueSeedExecuted(message) {
    const result = originalExecuted?.apply(this, arguments);
    captureActualSeed(this, message);
    return result;
  };
}

function allDirectors() {
  return (app.graph?._nodes || []).filter((node) => node?.comfyClass === TARGET);
}

api.addEventListener("execution_start", ({ detail }) => {
  activePromptId = promptId(detail);
});

api.addEventListener("executed", ({ detail }) => {
  const id = promptId(detail);
  const actual = actualSeedByPrompt.get(id);
  if (!actual) return;
  const outputNode = app.graph?.getNodeById?.(Number(detail?.node));
  if (!outputNode || !FINAL_OUTPUTS.has(outputNode.comfyClass)) return;
  const director = app.graph?.getNodeById?.(Number(actual.nodeId));
  if (!director || !isNodeDownstream(app.graph?.links, director.id, outputNode.id)) return;

  // Run after all synchronous "executed" listeners and Studio's render
  // microtask, so listener registration order cannot make the next queued seed
  // overwrite metadata for the image that just finished.
  setTimeout(() => {
    if (outputNode.comfyClass !== "H3StudioComparisonView" && director.__h3studioFinalImage) {
      director.__h3studioFinalImage.seed = actual.seed;
      const metadata = director.__h3studioPanel?.querySelector?.(".h3s-final-metadata");
      if (metadata) {
        const image = director.__h3studioFinalImage;
        metadata.textContent = image.width && image.height
          ? `Seed ${actual.seed} · ${image.width} × ${image.height} · ${image.profile}`
          : `Seed ${actual.seed} · ${image.profile}`;
      }
    }
  }, 0);
});

api.addEventListener("execution_success", ({ detail }) => {
  const id = promptId(detail);
  if (id) actualSeedByPrompt.delete(id);
  if (id === activePromptId) activePromptId = "";
});

for (const eventName of ["execution_error", "execution_interrupted"]) {
  api.addEventListener(eventName, ({ detail }) => {
    // Failed/aborted jobs consumed a queue reservation but the legacy Studio
    // execution_success advancement path will not run. Drop one reservation so
    // a later successful job is not suppressed accidentally.
    for (const node of allDirectors()) releaseFailedReservation(node);
    const id = promptId(detail);
    if (id) actualSeedByPrompt.delete(id);
    if (id === activePromptId) activePromptId = "";
  });
}

app.registerExtension({
  name: "H3Studio.QueueSeedV7",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== TARGET) return;
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function h3studioQueueSeedCreated() {
      const result = originalCreated?.apply(this, arguments);
      // Run after Studio's main extension has created/hidden its native widgets.
      setTimeout(() => installQueueSeed(this), 0);
      return result;
    };
  },
  loadedGraphNode(node) {
    if (node?.comfyClass === TARGET) setTimeout(() => installQueueSeed(node), 0);
  },
});
