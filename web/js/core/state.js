export const STATE_SCHEMA_VERSION = 3;
export const MAX_REFERENCES = 9;

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
  ["lightx_er_sde_4", "LightX v0.1 · ER-SDE 4"],
  ["lightx_sa_solver_4", "LightX v0.1 · SA-Solver 4"],
]);

export const FRAME_PROFILES = Object.freeze([
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

export function defaultState() {
  return {
    schema_version: STATE_SCHEMA_VERSION,
    prompt: "",
    references: [],
    prompt_options: {
      enhance_mode: "compile_only",
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
      aspect_ratio: "1:1",
      megapixels: 1,
      custom_width: 1024,
      custom_height: 1024,
      cap_native_resolution: true,
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
    description: String(source.description || ""),
    enabled: source.enabled !== false,
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
  promptOptions.enhance_mode = choice(promptOptions.enhance_mode, ["off", "compile_only", "vlm"], "compile_only");
  promptOptions.adherence = clamp(promptOptions.adherence, 0, 1, 0.85);
  promptOptions.detail_level = choice(promptOptions.detail_level, ["concise", "detailed", "maximum"], "detailed");
  promptOptions.analyzer_max_tokens = Math.round(clamp(promptOptions.analyzer_max_tokens, 128, 8192, 1800));
  generation.mode = choice(generation.mode, ["auto", "text_to_image", "image_to_image", "reference_edit"], "auto");
  generation.route = choice(generation.route, ["auto", "fl2va", "ref2va"], "auto");
  generation.seed = Math.max(0, Math.trunc(Number(generation.seed) || 0));
  generation.aspect_ratio = choice(generation.aspect_ratio, Object.keys(ASPECT_RATIOS), "1:1");
  generation.megapixels = clamp(generation.megapixels, 0.2, 2, 1);
  generation.custom_width = Math.round(clamp(generation.custom_width, 32, 16384, 1024));
  generation.custom_height = Math.round(clamp(generation.custom_height, 32, 16384, 1024));
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
    prompt: String(source.prompt || ""),
    references,
    prompt_options: promptOptions,
    generation,
    ui: { ...defaults.ui, ...object(source.ui) },
  };
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

export function serializeState(state) {
  return JSON.stringify(normalizeState(state));
}

export function rewriteMentions(prompt, ordinalMap) {
  return String(prompt || "").replace(/(^|[^\w@])@Image\s*([1-9]\d*)\b/gi, (whole, prefix, ordinal) => {
    const mapped = ordinalMap[Number(ordinal)] ?? Number(ordinal);
    return `${prefix}@Image ${mapped}`;
  });
}

export function planResolution(aspectRatio, megapixels, customWidth = 1024, customHeight = 1024, capNative = true) {
  const ratioPair = ASPECT_RATIOS[aspectRatio] || ASPECT_RATIOS["1:1"];
  const ratio = aspectRatio === "custom"
    ? clamp(customWidth, 32, 16384, 1024) / clamp(customHeight, 32, 16384, 1024)
    : ratioPair[0] / ratioPair[1];
  const requested = clamp(megapixels, 0.2, 2, 1);
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
