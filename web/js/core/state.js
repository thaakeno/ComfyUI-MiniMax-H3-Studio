export const STATE_SCHEMA_VERSION = 10;
export const MAX_REFERENCES = 9;
export const MIN_MEGAPIXELS = 0.2;
export const MAX_MEGAPIXELS = 8.5;
export const UHD_4K_MEGAPIXELS = 8.2944;
export const MEGAPIXEL_STEP = 0.05;

export const ASPECT_RATIOS = Object.freeze({
  "1:1": [1, 1],
  "4:5": [4, 5],
  "5:4": [5, 4],
  "3:4": [3, 4],
  "4:3": [4, 3],
  "2:3": [2, 3],
  "3:2": [3, 2],
  "9:16": [9, 16],
  "16:9": [16, 9],
  "21:9": [21, 9],
  custom: [0, 0],
});

export const ROLES = Object.freeze([
  "auto",
  "identity",
  "character",
  "face",
  "style",
  "composition",
  "pose",
  "outfit",
  "object",
  "environment",
  "layout",
  "typography",
  "color_palette",
  "lighting",
  "texture",
]);

export const RETENTION = Object.freeze([
  "attribute_transfer",
  "fully_preserved",
  "partially_preserved",
  "reference_only",
]);

export const SAMPLING_PROFILES = Object.freeze([
  ["base_quality_20", "Base Quality · RES 20"],
  ["base_balanced_12", "Base Balanced · RES 12"],
  ["lightx_er_sde_4", "LightX v0.1 · ER-SDE 4 · empirical"],
  ["lightx_sa_solver_4", "LightX v0.1 · SA-Solver 4 · empirical"],
  ["pdd_ref2va_4_600", "PDD REF2VA · 4-step · ckpt 600"],
  ["pdd_ref2va_4_900", "PDD REF2VA · 4-step · ckpt 900"],
]);

export const FRAME_PROFILES = Object.freeze([
  ["image_vae_1", "Experimental Image VAE Â· 1 frame"],
  ["recommended_5", "Recommended · 5 frames"],
  ["balanced_9", "Balanced · 9 frames"],
  ["quality_13", "High Quality · 13 frames"],
  ["maximum_20", "Maximum · 20 frames"],
]);

export function backendResolutionValue(value) {
  return String(value || "").toLowerCase() === "custom" ? "Custom" : String(value || "480P");
}

export function clamp(value, minimum, maximum, fallback = minimum) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.min(maximum, Math.max(minimum, number));
}

export function roundToMultiple(value, multiple = 32) {
  return Math.max(multiple, Math.round(Number(value) / multiple) * multiple);
}

export function formatMegapixels(value) {
  return `${clamp(value, MIN_MEGAPIXELS, MAX_MEGAPIXELS, 1).toFixed(2)} MP`;
}

export function defaultState() {
  return {
    schema_version: STATE_SCHEMA_VERSION,
    prompt: "",
    references: [],
    prompt_options: {
      enhance_mode: "compile_only",
      analyze_images: false,
      deep_enhancement: false,
      analyzer_resolution: 512,
      adherence: 0.85,
      detail_level: "detailed",
      preserve_user_text: true,
      infer_roles: true,
      system_instruction: "",
      analyzer_model: "",
      analyzer_device: "auto",
      analyzer_quantization: "auto",
      analyzer_max_tokens: 1800,
      analyzer_keep_loaded: false,
    },
    generation: {
      mode: "auto",
      route: "auto",
      seed: 0,
      seed_locked: false,
      aspect_ratio: "1:1",
      megapixels: 1,
      custom_width: 1024,
      custom_height: 1024,
      cap_native_resolution: false,
      sampling_profile: "base_quality_20",
      frame_profile: "recommended_5",
      frame_selection: "decode_recommended",
      reference_short_edge: 2048,
      source_image_ordinal: 1,
    },
    ui: {
      advanced_open: false,
      reference_details: {},
    },
  };
}

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function choice(value, choices, fallback) {
  const text = String(value ?? fallback);
  return choices.includes(text) ? text : fallback;
}

export function normalizeReference(value, ordinal) {
  const source = object(value);
  const storageName = String(source.storage_name || "").replaceAll("\\", "/").trim();
  const displayName = String(source.filename || storageName || `image_${ordinal}.png`).split(/[\\/]/).pop().replace(/\s+\[(?:input|output|temp)\]$/i, "");
  return {
    id: String(source.id || `ref_${ordinal}`),
    filename: displayName,
    storage_name: storageName,
    ordinal,
    role: choice(source.role, ROLES, "auto"),
    retention: choice(source.retention, RETENTION, "attribute_transfer"),
    role_auto: source.role_auto == null ? choice(source.role, ROLES, "auto") === "auto" : source.role_auto === true,
    retention_auto: source.retention_auto == null ? choice(source.role, ROLES, "auto") === "auto" : source.retention_auto === true,
    description: String(source.description || ""),
    description_auto: source.description_auto == null ? !String(source.description || "").trim() : source.description_auto === true,
    enabled: source.enabled !== false,
    width: Number.isFinite(Number(source.width)) && Number(source.width) > 0 ? Math.round(Number(source.width)) : null,
    height: Number.isFinite(Number(source.height)) && Number(source.height) > 0 ? Math.round(Number(source.height)) : null,
    fingerprint: String(source.fingerprint || "").trim() || null,
    thumbnail: String(source.thumbnail || "").trim(),
    tags: Array.isArray(source.tags) ? [...new Set(source.tags.map((tag) => String(tag).trim()).filter(Boolean))] : [],
    source_node_id: source.source_node_id == null ? null : String(source.source_node_id),
    source_slot: Math.max(0, Number(source.source_slot) || 0),
  };
}

export function migrateState(value) {
  const source = object(value);
  const version = Number(source.schema_version) || 1;
  if (version >= STATE_SCHEMA_VERSION) return source;
  const migrated = { ...source };
  const settings = object(migrated.settings);
  const generation = { ...object(migrated.generation) };
  const promptOptions = { ...object(migrated.prompt_options) };
  for (const key of ["mode", "route", "seed", "aspect_ratio", "megapixels", "custom_width", "custom_height", "sampling_profile"]) {
    if (key in settings && !(key in generation)) generation[key] = settings[key];
  }
  for (const key of ["enhance_mode", "adherence", "detail_level", "analyzer_model"]) {
    if (key in settings && !(key in promptOptions)) promptOptions[key] = settings[key];
  }
  generation.cap_native_resolution = false;
  migrated.schema_version = STATE_SCHEMA_VERSION;
  migrated.generation = generation;
  migrated.prompt_options = promptOptions;
  delete migrated.settings;
  return migrated;
}

export function normalizeState(value) {
  const defaults = defaultState();
  const source = migrateState(object(value));
  const promptOptions = { ...defaults.prompt_options, ...object(source.prompt_options) };
  const generation = { ...defaults.generation, ...object(source.generation) };
  if (promptOptions.enhance_mode === "vlm") {
    promptOptions.enhance_mode = "compile_only";
    promptOptions.analyze_images = true;
  } else {
    promptOptions.enhance_mode = choice(promptOptions.enhance_mode, ["off", "single_prompt", "compile_only"], "compile_only");
    promptOptions.analyze_images = promptOptions.analyze_images === true;
  }
  promptOptions.deep_enhancement = promptOptions.deep_enhancement === true;
  promptOptions.adherence = clamp(promptOptions.adherence, 0, 1, 0.85);
  promptOptions.analyzer_resolution = Math.round(clamp(promptOptions.analyzer_resolution, 0, 1024, 512));
  promptOptions.detail_level = choice(promptOptions.detail_level, ["concise", "detailed", "maximum"], "detailed");
  promptOptions.analyzer_max_tokens = Math.round(clamp(promptOptions.analyzer_max_tokens, 128, 8192, 1800));
  generation.mode = choice(generation.mode, ["auto", "text_to_image", "image_to_image", "reference_edit"], "auto");
  generation.route = choice(generation.route, ["auto", "fl2va", "ref2va"], "auto");
  generation.seed = Math.max(0, Math.trunc(Number(generation.seed) || 0));
  generation.seed_locked = generation.seed_locked === true;
  generation.aspect_ratio = choice(generation.aspect_ratio, Object.keys(ASPECT_RATIOS), "1:1");
  generation.megapixels = clamp(generation.megapixels, MIN_MEGAPIXELS, MAX_MEGAPIXELS, 1);
  generation.custom_width = Math.round(clamp(generation.custom_width, 32, 16384, 1024));
  generation.custom_height = Math.round(clamp(generation.custom_height, 32, 16384, 1024));
  generation.cap_native_resolution = generation.cap_native_resolution === true;
  generation.sampling_profile = ({
    turbo_er_sde_6: "lightx_er_sde_4",
    turbo_sa_solver_4: "lightx_sa_solver_4",
  })[generation.sampling_profile] || generation.sampling_profile;
  generation.sampling_profile = choice(generation.sampling_profile, SAMPLING_PROFILES.map(([key]) => key), "base_quality_20");
  generation.frame_profile = choice(generation.frame_profile, FRAME_PROFILES.map(([key]) => key), "recommended_5");
  const references = Array.isArray(source.references)
    ? source.references.slice(0, MAX_REFERENCES).map((reference, index) => normalizeReference(reference, index + 1))
    : [];
  return {
    ...defaults,
    ...source,
    schema_version: STATE_SCHEMA_VERSION,
    prompt: canonicalizeMentions(source.prompt),
    references,
    prompt_options: promptOptions,
    generation,
    ui: { ...defaults.ui, ...object(source.ui) },
  };
}

export function applyReferenceInferences(value, roles = [], retentions = [], descriptions = []) {
  const state = normalizeState(value);
  const changes = {};
  state.references = state.references.map((reference, index) => {
    const nextRole = String(roles[index] || reference.role);
    const nextRetention = String(retentions[index] || reference.retention);
    const nextDescription = String(descriptions[index] || "").trim();
    const canUpdateRole = reference.role === "auto" || reference.role_auto === true;
    const canUpdateRetention = reference.retention_auto === true || reference.role === "auto";
    const updated = {
      ...reference,
      role: canUpdateRole ? choice(nextRole, ROLES, reference.role) : reference.role,
      retention: canUpdateRetention ? choice(nextRetention, RETENTION, reference.retention) : reference.retention,
      role_auto: canUpdateRole,
      retention_auto: canUpdateRetention,
      description: nextDescription && (reference.description_auto === true || !reference.description.trim())
        ? nextDescription
        : reference.description,
      description_auto: nextDescription && (reference.description_auto === true || !reference.description.trim())
        ? true
        : reference.description_auto,
    };
    if (
      (canUpdateRole && updated.role !== reference.role)
      || (canUpdateRetention && updated.retention !== reference.retention)
      || updated.description !== reference.description
    ) {
      changes[index] = { role: updated.role, retention: updated.retention };
      if (updated.description !== reference.description) changes[index].analyzed = true;
    }
    return updated;
  });
  return { state, changes };
}

export function parseState(value) {
  if (!value) return defaultState();
  if (typeof value === "object") return normalizeState(value);
  try {
    return normalizeState(JSON.parse(String(value)));
  } catch {
    return defaultState();
  }
}

export function advanceSeedAfterGeneration(generation, randomizer) {
  const current = Math.max(0, Math.trunc(Number(generation?.seed) || 0));
  if (generation?.seed_locked === true) return { ...generation, seed: current, seed_locked: true };
  let next = Math.max(0, Math.trunc(Number(randomizer?.()) || 0)) % Number.MAX_SAFE_INTEGER;
  if (next === current) next = (current + 1) % Number.MAX_SAFE_INTEGER;
  return { ...generation, seed: next, seed_locked: false };
}

export function restorePersistedState(primary, backup) {
  const failures = [];
  for (const [source, value] of [["widget", primary], ["property", backup]]) {
    if (value == null || String(value).trim() === "") continue;
    try {
      const decoded = typeof value === "object" ? value : JSON.parse(String(value));
      return {
        state: normalizeState(decoded),
        source,
        error: failures[0]?.error || null,
        recovery: failures[0]?.value || "",
      };
    } catch (error) {
      failures.push({ source, value: String(value), error });
    }
  }
  return {
    state: defaultState(),
    source: "default",
    error: failures.length
      ? new Error(`Could not restore H3 Studio state from ${failures.map(({ source }) => source).join(" or ")}.`)
      : null,
    recovery: failures[0]?.value || "",
  };
}

export function serializeState(state) {
  return JSON.stringify(normalizeState(state));
}

export function validateGenerationContract(value) {
  const state = normalizeState(value);
  const { mode, route, sampling_profile: profile } = state.generation;
  const referenceCount = state.references.filter((reference) => reference.enabled !== false).length;
  const isPdd = String(profile).startsWith("pdd_ref2va_");
  if (mode === "image_to_image" && referenceCount === 0) return "Image-to-image requires at least one enabled reference image.";
  if (mode === "reference_edit" && referenceCount === 0) return "Reference mix/edit requires at least one enabled reference image.";
  if (isPdd && referenceCount === 0) return "PDD REF2VA requires at least one enabled reference image.";
  if (isPdd && ["text_to_image", "image_to_image"].includes(mode)) {
    return "PDD REF2VA supports reference mix/edit; use Auto or Reference mix/edit mode.";
  }
  if (isPdd && route === "fl2va") return "PDD is trained for REF2VA and cannot run on a forced FL2VA route.";
  let effectiveMode = mode;
  if (mode === "auto") {
    effectiveMode = referenceCount === 0
      ? "text_to_image"
      : referenceCount === 1 && !isPdd ? "image_to_image" : "reference_edit";
  }
  const expectedRoute = effectiveMode === "reference_edit" ? "ref2va" : "fl2va";
  if (route !== "auto" && route !== expectedRoute) {
    return `Forced ${route.toUpperCase()} is incompatible with ${effectiveMode.replaceAll("_", " ")} mode; use Auto.`;
  }
  return null;
}

export function missingReferenceOrdinals(value) {
  const state = normalizeState(value);
  const enabled = new Set(
    state.references
      .filter((reference) => reference.enabled !== false)
      .map((reference) => Number(reference.ordinal)),
  );
  const missing = new Set();
  String(state.prompt || "").replace(/(^|[^\w@])@Image[_\s]*([1-9]\d*)\b/gi, (whole, prefix, ordinal) => {
    const number = Number(ordinal);
    if (!enabled.has(number)) missing.add(number);
    return whole;
  });
  return [...missing].sort((left, right) => left - right);
}

export function removeReferenceMentions(prompt, ordinals) {
  const stale = new Set((ordinals || []).map(Number));
  return String(prompt || "")
    .replace(/(^|[^\w@])@Image[_\s]*([1-9]\d*)\b/gi, (whole, prefix, ordinal) => (
      stale.has(Number(ordinal)) ? prefix : whole
    ))
    .replace(/[ \t]+([,.;:!?])/g, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/[ \t]+$/gm, "")
    .trim();
}

export function rewriteMentions(prompt, ordinalMap) {
  return String(prompt || "").replace(/(^|[^\w@])@Image[_\s]*([1-9]\d*)\b/gi, (whole, prefix, ordinal) => {
    const mapped = ordinalMap[Number(ordinal)] ?? Number(ordinal);
    return `${prefix}@Image${mapped}`;
  });
}

export function canonicalizeMentions(prompt) {
  return rewriteMentions(prompt, {});
}

export function planResolution(aspectRatio, megapixels, customWidth = 1024, customHeight = 1024, capNative = false) {
  const ratioPair = ASPECT_RATIOS[aspectRatio] || ASPECT_RATIOS["1:1"];
  const ratio = aspectRatio === "custom"
    ? clamp(customWidth, 32, 16384, 1024) / clamp(customHeight, 32, 16384, 1024)
    : ratioPair[0] / ratioPair[1];
  const requested = clamp(megapixels, MIN_MEGAPIXELS, MAX_MEGAPIXELS, 1);
  const nativeCap = 768 * 1344;
  const target = capNative ? Math.min(requested * 1_000_000, nativeCap) : requested * 1_000_000;
  let width = roundToMultiple(Math.sqrt(target * ratio));
  let height = roundToMultiple(Math.sqrt(target / ratio));
  if (capNative && width * height > nativeCap) {
    const scale = Math.sqrt(nativeCap / (width * height));
    width = Math.max(32, Math.floor((width * scale) / 32) * 32);
    height = Math.max(32, Math.floor((height * scale) / 32) * 32);
  }
  return {
    width,
    height,
    requestedMegapixels: requested,
    actualMegapixels: (width * height) / 1_000_000,
    capped: capNative && requested * 1_000_000 > nativeCap,
    aspectRatio,
  };
}
