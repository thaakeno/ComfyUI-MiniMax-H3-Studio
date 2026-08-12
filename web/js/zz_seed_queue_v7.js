import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

import {
  normalizeState,
  releaseSeedQueueReservation,
  reserveSeedAfterQueue,
  restorePersistedState,
  serializeState,
} from "./core/state.js";

const TARGET = "H3StudioDirector";
const STATE_PROPERTY = "h3studio_state";
const installedNodes = new Set();

function widget(node, name) {
  return node?.widgets?.find((candidate) => candidate.name === name) || null;
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
}

function allDirectors() {
  return (app.graph?._nodes || []).filter((node) => node?.comfyClass === TARGET);
}

for (const eventName of ["execution_error", "execution_interrupted"]) {
  api.addEventListener(eventName, () => {
    // Failed/aborted jobs consumed a queue reservation but the legacy Studio
    // execution_success advancement path will not run. Drop one reservation so
    // a later successful job is not suppressed accidentally.
    for (const node of allDirectors()) releaseFailedReservation(node);
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
