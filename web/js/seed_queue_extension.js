import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

import { advanceSeedAfterGeneration, normalizeState, serializeState } from "./core/state.js";

const TARGET = "H3StudioDirector";
const STATE_PROPERTY = "h3studio_state";
const WRAP_FLAG = "__h3studioSeedQueueWrapped";

function widget(node, name) {
  return node?.widgets?.find((candidate) => candidate.name === name) || null;
}

function randomSeed() {
  const values = new Uint32Array(2);
  globalThis.crypto?.getRandomValues?.(values);
  const combined = values[0] * 0x200000 + (values[1] & 0x1fffff);
  return combined || Math.floor(Math.random() * Number.MAX_SAFE_INTEGER);
}

function serializedState(apiNode, liveNode) {
  const raw = apiNode?.inputs?.studio_state;
  if (raw && typeof raw === "string") {
    try {
      return normalizeState(JSON.parse(raw));
    } catch {
      // Fall through to the live property/widget recovery below.
    }
  }
  const liveRaw = widget(liveNode, "studio_state")?.value || liveNode?.properties?.[STATE_PROPERTY];
  if (liveRaw && typeof liveRaw === "string") {
    try {
      return normalizeState(JSON.parse(liveRaw));
    } catch {
      // Fall through to a normalized empty object.
    }
  }
  return normalizeState({});
}

function applyLiveSeed(liveNode, state) {
  if (!liveNode) return;
  const normalized = normalizeState(state);
  const serialized = serializeState(normalized);
  const seedWidget = widget(liveNode, "seed");
  const stateWidget = widget(liveNode, "studio_state");
  if (seedWidget) seedWidget.value = normalized.generation.seed;
  if (stateWidget) stateWidget.value = serialized;
  liveNode.properties ||= {};
  liveNode.properties[STATE_PROPERTY] = serialized;
  liveNode.__h3studioState = normalized;
  liveNode.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}

function reserveNextSeeds(data) {
  const output = data?.output;
  if (!output || typeof output !== "object") return [];

  const reservations = [];
  for (const [nodeId, apiNode] of Object.entries(output)) {
    if (apiNode?.class_type !== TARGET) continue;
    const liveNode = app.graph?.getNodeById?.(Number(nodeId));
    const queuedState = serializedState(apiNode, liveNode);
    const queuedSeed = Math.max(0, Math.trunc(Number(apiNode?.inputs?.seed ?? queuedState.generation.seed) || 0));
    queuedState.generation.seed = queuedSeed;

    if (queuedState.generation.seed_locked === true) {
      console.info(`[H3 Studio] queued locked seed=${queuedSeed} node=${nodeId}`);
      continue;
    }

    const nextState = normalizeState(queuedState);
    nextState.generation = advanceSeedAfterGeneration(nextState.generation, randomSeed);
    const nextSeed = nextState.generation.seed;
    applyLiveSeed(liveNode, nextState);
    reservations.push({ nodeId, liveNode, queuedState, queuedSeed, nextSeed });
    console.info(`[H3 Studio] queued seed=${queuedSeed} | reserved next=${nextSeed} | node=${nodeId}`);
  }
  return reservations;
}

function rollbackReservations(reservations) {
  for (const reservation of reservations) {
    const current = Number(widget(reservation.liveNode, "seed")?.value);
    // Never roll back over a later queue click that has already reserved another seed.
    if (current !== reservation.nextSeed) continue;
    applyLiveSeed(reservation.liveNode, reservation.queuedState);
  }
}

if (!api[WRAP_FLAG]) {
  const originalQueuePrompt = api.queuePrompt.bind(api);
  api.queuePrompt = async function h3studioQueuePrompt(number, data, options) {
    // FAIL-OPEN ORDERING IS INTENTIONAL.
    // ComfyUI's real queuePrompt starts the /prompt request synchronously before
    // its first await. Dispatch that request first so H3 Studio seed bookkeeping
    // can never turn the Run button into a no-op.
    const request = originalQueuePrompt(number, data, options);

    // app.queuePrompt has already serialized `data` at this point. Mutating the
    // live Director now cannot change the submitted job; it only reserves the
    // next seed for a subsequent click while this request/job is in flight.
    let reservations = [];
    try {
      reservations = reserveNextSeeds(data);
    } catch (error) {
      // Seed reservation is optional UI bookkeeping. Never block generation if
      // a custom widget/state shape changes underneath us.
      console.warn("[H3 Studio] seed reservation failed after queue dispatch; generation continues", error);
    }

    try {
      return await request;
    } catch (error) {
      rollbackReservations(reservations);
      throw error;
    }
  };
  api[WRAP_FLAG] = true;
}
