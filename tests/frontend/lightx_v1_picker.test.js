import assert from "node:assert/strict";
import test from "node:test";

import {
  SAMPLING_PROFILES,
  defaultState,
  normalizeState,
  validateGenerationContract,
} from "../../web/js/core/state.js";

test("Director exposes the official LightX v1.0 8-step profile", () => {
  assert.equal(
    SAMPLING_PROFILES.some(([key, label]) => (
      key === "lightx_v1_fl2v_8" && label === "LightX v1.0 · FL2V 8-step · official ComfyUI"
    )),
    true,
  );

  const state = defaultState();
  state.generation.sampling_profile = "lightx_v1_fl2v_8";
  assert.equal(normalizeState(state).generation.sampling_profile, "lightx_v1_fl2v_8");
});

test("frontend rejects LightX v1 on REF2VA just like the backend", () => {
  const state = defaultState();
  state.generation.sampling_profile = "lightx_v1_fl2v_8";
  state.generation.mode = "reference_edit";
  state.references = [{ id: "1", filename: "a.png", ordinal: 1, enabled: true }];
  assert.match(validateGenerationContract(state), /FL2V adapter/);
});
