import assert from "node:assert/strict";
import test from "node:test";

import {
  advanceSeedAfterGeneration,
  normalizeState,
  releaseSeedQueueReservation,
  reserveSeedAfterQueue,
} from "../../web/js/core/state.js";

function generation(seed = 42, locked = false) {
  return normalizeState({ generation: { seed, seed_locked: locked } }).generation;
}

test("three rapid queue reservations serialize three distinct seeds", () => {
  let state = generation(42, false);
  const serializedSeeds = [];
  for (const next of [100, 200, 300]) {
    serializedSeeds.push(state.seed);
    state = reserveSeedAfterQueue(state, () => next);
  }
  assert.deepEqual(serializedSeeds, [42, 100, 200]);
  assert.equal(new Set(serializedSeeds).size, 3);
  assert.equal(state.seed, 300);
  assert.equal(state.seed_queue_reservations, 3);
});

test("execution_success consumes queue reservations without advancing twice", () => {
  let state = generation(42, false);
  state = reserveSeedAfterQueue(state, () => 100);
  state = reserveSeedAfterQueue(state, () => 200);
  state = reserveSeedAfterQueue(state, () => 300);

  state = advanceSeedAfterGeneration(state, () => 900);
  assert.equal(state.seed, 300);
  assert.equal(state.seed_queue_reservations, 2);
  state = advanceSeedAfterGeneration(state, () => 901);
  assert.equal(state.seed, 300);
  assert.equal(state.seed_queue_reservations, 1);
  state = advanceSeedAfterGeneration(state, () => 902);
  assert.equal(state.seed, 300);
  assert.equal(state.seed_queue_reservations, 0);
});

test("failed or interrupted jobs release one reservation without changing the visible seed", () => {
  let state = generation(7, false);
  state = reserveSeedAfterQueue(state, () => 8);
  state = reserveSeedAfterQueue(state, () => 9);
  state = releaseSeedQueueReservation(state);
  assert.equal(state.seed, 9);
  assert.equal(state.seed_queue_reservations, 1);
});

test("locked seeds never reserve or advance", () => {
  const state = reserveSeedAfterQueue(generation(123, true), () => 999);
  assert.equal(state.seed, 123);
  assert.equal(state.seed_locked, true);
  assert.equal(state.seed_queue_reservations, 0);
});
