import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

import {
  applyReferenceInferences,
  ASPECT_RATIOS,
  FRAME_PROFILES,
  MAX_MEGAPIXELS,
  MAX_REFERENCES,
  MEGAPIXEL_STEP,
  MIN_MEGAPIXELS,
  RETENTION,
  ROLES,
  SAMPLING_PROFILES,
  advanceSeedAfterGeneration,
  formatMegapixels,
  missingReferenceOrdinals,
  normalizeState,
  planResolution,
  removeReferenceMentions,
  restorePersistedState,
  serializeState,
  validateGenerationContract,
} from "./core/state.js";
import { element, field, iconButton, numberControl, rangeControl, selectControl } from "./core/dom.js";
import { executedImageUrl, isNodeDownstream } from "./core/final_output.js";
import { STUDIO_PANEL_HEIGHT, initialStudioNodeSize, studioPanelSize } from "./core/layout.js";
import { openImageLightbox } from "./core/lightbox.js";
import { installTheme } from "./core/theme.js";
import {
  chooseImageFiles,
  fullMediaUrl,
  imageFilesFromTransfer,
  mediaUrlForStorage,
  previewUrlForStorage,
  uploadImages,
} from "./features/image_upload.js";

const TARGET = "H3StudioDirector";
const LINKS_PROPERTY = "h3studio_virtual_media_links";
const STATE_PROPERTY = "h3studio_state";
const STATE_RECOVERY_PROPERTY = "h3studio_state_recovery";
const VISIBLE_STUDIO_WIDGETS = new Set(["prompt", "h3_prompt_mentions", "h3studio_controls"]);
const pendingSeedAdvances = new Map();
let activePromptId = "";

function widget(node, name) {
  return node.widgets?.find((candidate) => candidate.name === name) || null;
}

function setWidget(node, name, value, invoke = false) {
  const target = widget(node, name);
  if (!target || target.value === value) return;
  target.value = value;
  if (invoke) target.callback?.(value, app.canvas, node, [0, 0], {});
}

function randomSeed() {
  const values = new Uint32Array(2);
  globalThis.crypto?.getRandomValues?.(values);
  const combined = values[0] * 0x200000 + (values[1] & 0x1fffff);
  return combined || Math.floor(Math.random() * Number.MAX_SAFE_INTEGER);
}

function hideWidget(target) {
  if (!target) return;
  if (!target.__h3studioHidden) {
    target.__h3studioHidden = true;
    target.__h3studioComputeSize = target.computeSize;
    target.__h3studioType = target.type;
  }
  target.computeSize = () => [0, -4];
  target.hidden = true;
  target.type = "h3studio_hidden";
}

function restoreWidgetHiddenByStudio(target) {
  if (!target?.__h3studioHidden) return;
  target.computeSize = target.__h3studioComputeSize;
  target.hidden = false;
  target.type = target.__h3studioType;
  target.__h3studioHidden = false;
}

function enforceNativeWidgetVisibility(node) {
  for (const target of node.widgets || []) {
    // h3studio_ui.js replaces the hidden native prompt widget with the
    // h3_prompt_mentions DOM editor. Keep both names exempt so either frontend
    // initialization order leaves exactly one usable prompt surface visible.
    if (VISIBLE_STUDIO_WIDGETS.has(target.name)) {
      restoreWidgetHiddenByStudio(target);
      continue;
    }
    hideWidget(target);
  }
}

function sourceNode(link) {
  if (!link) return null;
  return app.graph?.getNodeById?.(Number(link.source_id)) || null;
}

function plainFilename(value) {
  const candidate = typeof value === "object" ? value?.filename || value?.name : value;
  const text = String(candidate || "").trim();
  if (!text || /^(data:|blob:|https?:)/i.test(text)) return "";
  return text.split(/[\\/]/).pop() || "";
}

function sourceFilename(source, ordinal) {
  const preferred = ["image", "filename", "file", "upload"];
  const widgets = source?.widgets || [];
  for (const name of preferred) {
    const value = widgets.find((candidate) => String(candidate.name).toLowerCase() === name)?.value;
    const filename = plainFilename(value);
    if (filename) return filename;
  }
  for (const candidate of widgets) {
    const filename = plainFilename(candidate.value);
    if (/\.(png|jpe?g|webp|gif|bmp|tiff?)$/i.test(filename)) return filename;
  }
  return plainFilename(source?.properties?.filename) || `image_${ordinal}.png`;
}

function sourcePreview(source) {
  const direct = source?.imgs?.[0]?.src || source?.image?.src;
  if (direct) return direct;
  const widgetValue = source?.widgets?.find((candidate) => String(candidate.name).toLowerCase() === "image")?.value;
  const filename = typeof widgetValue === "object" ? widgetValue?.filename || widgetValue?.name : widgetValue;
  if (!filename || typeof filename !== "string") return "";
  const type = typeof widgetValue === "object" ? widgetValue.type || "input" : "input";
  const subfolder = typeof widgetValue === "object" ? widgetValue.subfolder || "" : "";
  const query = new URLSearchParams({ filename, type, subfolder, preview: "webp;90" });
  return `/view?${query.toString()}`;
}

function promptId(detail) {
  return String(detail?.prompt_id || detail?.promptId || activePromptId || "");
}

function queueSeedAdvance(node) {
  if (stateFromNode(node).generation.seed_locked) return;
  const id = activePromptId;
  if (!id) return;
  const nodes = pendingSeedAdvances.get(id) || new Set();
  nodes.add(node);
  pendingSeedAdvances.set(id, nodes);
}

function finishSeedAdvances(detail) {
  const id = promptId(detail);
  const nodes = pendingSeedAdvances.get(id);
  if (!nodes) return;
  pendingSeedAdvances.delete(id);
  for (const node of nodes) {
    const state = stateFromNode(node);
    state.generation = advanceSeedAfterGeneration(state.generation, randomSeed);
    applyState(node, state, false);
    renderPanel(node);
  }
}

api.addEventListener("execution_start", ({ detail }) => {
  activePromptId = promptId(detail);
});
api.addEventListener("execution_success", ({ detail }) => {
  finishSeedAdvances(detail);
  if (promptId(detail) === activePromptId) activePromptId = "";
});
for (const eventName of ["execution_error", "execution_interrupted"]) {
  api.addEventListener(eventName, ({ detail }) => {
    const id = promptId(detail);
    pendingSeedAdvances.delete(id);
    if (id === activePromptId) activePromptId = "";
  });
}

function sourceMedia(source) {
  const widgetValue = source?.widgets?.find((candidate) => String(candidate.name).toLowerCase() === "image")?.value;
  const filename = typeof widgetValue === "object" ? widgetValue?.filename || widgetValue?.name : widgetValue;
  if (!filename || typeof filename !== "string") {
    return fullMediaUrl(source?.imgs?.[0]?.src || source?.image?.src || "");
  }
  const type = typeof widgetValue === "object" ? widgetValue.type || "input" : "input";
  const subfolder = typeof widgetValue === "object" ? widgetValue.subfolder || "" : "";
  return `/view?${new URLSearchParams({ filename, type, subfolder }).toString()}`;
}

function persistentThumbnail(value) {
  const url = String(value || "").trim();
  return url.startsWith("/") ? url : "";
}

function normalizedLinks(node) {
  const raw = Array.isArray(node.properties?.[LINKS_PROPERTY]) ? node.properties[LINKS_PROPERTY] : [];
  const seen = new Set();
  return raw
    .filter((link) => String(link?.media_type || "image") === "image")
    .filter((link) => {
      const key = `${Number(link?.source_id)}:${Number(link?.source_slot) || 0}`;
      if (!Number.isFinite(Number(link?.source_id)) || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, MAX_REFERENCES)
    .map((link, index) => ({
      source_id: Number(link.source_id),
      source_slot: Number(link.source_slot) || 0,
      media_type: "image",
      order: index + 1,
    }));
}

function writeLinks(node, links) {
  node.properties ||= {};
  node.properties[LINKS_PROPERTY] = links.map((link, index) => ({ ...link, media_type: "image", order: index + 1 }));
}

function linkSignature(node) {
  return normalizedLinks(node).map((link) => `${link.source_id}:${link.source_slot}`).join("|");
}

function referenceForLink(previous, link, ordinal) {
  const bySource = previous.references.find(
    (reference) => String(reference.source_node_id) === String(link.source_id) && reference.source_slot === link.source_slot,
  );
  const byOrdinal = previous.references[ordinal - 1];
  const inherited = bySource || byOrdinal || {};
  const sameSource = Boolean(bySource);
  const liveThumbnail = persistentThumbnail(sourcePreview(sourceNode(link)));
  return {
    ...inherited,
    id: inherited.id || `node_${link.source_id}_${link.source_slot}`,
    filename: sourceFilename(sourceNode(link), ordinal),
    storage_name: "",
    thumbnail: liveThumbnail || (sameSource ? inherited.thumbnail || "" : ""),
    width: sameSource ? inherited.width ?? null : null,
    height: sameSource ? inherited.height ?? null : null,
    fingerprint: sameSource ? inherited.fingerprint ?? null : null,
    tags: sameSource ? inherited.tags || [] : [],
    ordinal,
    role: inherited.role || "auto",
    retention: inherited.retention || "attribute_transfer",
    role_auto: inherited.role_auto ?? (inherited.role || "auto") === "auto",
    retention_auto: inherited.retention_auto ?? (inherited.role || "auto") === "auto",
    description: sameSource ? inherited.description || "" : "",
    description_auto: sameSource ? inherited.description_auto ?? !String(inherited.description || "").trim() : true,
    enabled: true,
    source_node_id: String(link.source_id),
    source_slot: link.source_slot,
  };
}

function linkKey(link) {
  return `${Number(link.source_id)}:${Number(link.source_slot) || 0}`;
}

function writeLinksFromReferences(node, references) {
  const byKey = new Map(normalizedLinks(node).map((link) => [linkKey(link), link]));
  writeLinks(node, references
    .filter((reference) => reference.source_node_id != null)
    .map((reference) => byKey.get(`${Number(reference.source_node_id)}:${Number(reference.source_slot) || 0}`))
    .filter(Boolean));
}

function notifyReferenceChange(node) {
  globalThis.dispatchEvent?.(new CustomEvent("h3studio:references-changed", { detail: { nodeId: Number(node.id) } }));
}

function stateFromNode(node) {
  const restored = restorePersistedState(
    widget(node, "studio_state")?.value,
    node.properties?.[STATE_PROPERTY],
  );
  const persisted = restored.state;
  node.__h3studioStateError = restored.error?.message || "";
  if (restored.recovery) {
    node.properties ||= {};
    node.properties[STATE_RECOVERY_PROPERTY] ||= restored.recovery;
  }
  const links = normalizedLinks(node);
  const available = new Map(links.map((link) => [linkKey(link), link]));
  const used = new Set();
  const references = [];
  for (const reference of persisted.references) {
    if (reference.source_node_id == null) {
      if (reference.storage_name) references.push(reference);
      continue;
    }
    const key = `${Number(reference.source_node_id)}:${Number(reference.source_slot) || 0}`;
    const link = available.get(key);
    if (!link) continue;
    used.add(key);
    references.push(referenceForLink(persisted, link, references.length + 1));
  }
  for (const link of links) {
    if (used.has(linkKey(link))) continue;
    references.push(referenceForLink(persisted, link, references.length + 1));
  }
  persisted.prompt = String(widget(node, "prompt")?.value || persisted.prompt || "");
  const nativeSeed = Number(widget(node, "seed")?.value);
  if (Number.isFinite(nativeSeed) && nativeSeed >= 0) persisted.generation.seed = Math.trunc(nativeSeed);
  persisted.references = references.map((reference, index) => ({ ...reference, ordinal: index + 1 }));
  return normalizeState(persisted);
}

function applyState(node, state, dirty = true) {
  const normalized = normalizeState(state);
  const generation = normalized.generation;
  const options = normalized.prompt_options;
  const resolution = planResolution(
    generation.aspect_ratio,
    generation.megapixels,
    generation.custom_width,
    generation.custom_height,
    generation.cap_native_resolution,
  );
  setWidget(node, "mode", normalized.references.length || generation.mode === "reference_edit" ? "reference" : "image");
  setWidget(node, "resolution", "Custom");
  setWidget(node, "aspect_ratio", generation.aspect_ratio);
  setWidget(node, "width", resolution.width);
  setWidget(node, "height", resolution.height);
  setWidget(node, "megapixels", generation.megapixels);
  setWidget(node, "seed", generation.seed);
  setWidget(node, "enhance_mode", options.enhance_mode);
  setWidget(node, "adherence", options.adherence);
  setWidget(node, "route", generation.route);
  setWidget(node, "sampling_profile", generation.sampling_profile);
  setWidget(node, "frame_profile", generation.frame_profile);
  setWidget(node, "analyzer_model", options.analyzer_model);
  const serialized = serializeState(normalized);
  setWidget(node, "studio_state", serialized);
  node.properties ||= {};
  node.properties[STATE_PROPERTY] = serialized;
  for (let index = 1; index <= MAX_REFERENCES; index += 1) {
    const reference = normalized.references[index - 1];
    setWidget(node, `media_filename_${index}`, reference?.storage_name || reference?.filename || "");
    setWidget(node, `media_type_${index}`, "image");
    setWidget(node, `role_${index}`, reference?.role || "auto");
    setWidget(node, `retention_${index}`, reference?.retention || "attribute_transfer");
    setWidget(node, `description_${index}`, reference?.description || "");
  }
  node.__h3studioState = normalized;
  if (dirty) {
    node.__h3studioResult = null;
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
  }
  return normalized;
}

function executionValue(message, key) {
  const value = message?.[key];
  if (Array.isArray(value)) return value.map((item) => String(item ?? ""));
  return value == null ? [] : [String(value)];
}

function friendlyReferences(value) {
  return String(value || "")
    .replace(/<Picture\s+(\d+)>/gi, "@Image$1")
    .replace(/<Subject\s+(\d+)>/gi, "@Image$1");
}

function resultsSection(node) {
  const result = node.__h3studioResult;
  if (!result?.prompt) return null;
  const friendlyPrompt = friendlyReferences(result.prompt);
  const enhancedInstruction = friendlyReferences(result.enhancedPrompt || result.prompt);
  const copy = element("button", {
    className: "h3s-copy-result",
    type: "button",
    text: "Copy",
    attrs: { "aria-label": "Copy compiled prompt" },
    on: {
      click: async (event) => {
        event.preventDefault();
        event.stopPropagation();
        await globalThis.navigator?.clipboard?.writeText?.(enhancedInstruction);
        event.currentTarget.textContent = "Copied";
        setTimeout(() => { event.currentTarget.textContent = "Copy"; }, 1200);
      },
    },
  });
  const edit = element("button", {
    className: "h3s-copy-result",
    type: "button",
    text: "Edit result",
    attrs: { "aria-label": "Use generated instruction as the editable prompt" },
    on: {
      click: (event) => {
        event.preventDefault();
        event.stopPropagation();
        const state = stateFromNode(node);
        state.prompt = enhancedInstruction;
        state.prompt_options = { ...state.prompt_options, deep_enhancement: false };
        setWidget(node, "prompt", enhancedInstruction);
        node.__h3sDomWidget?.setValue?.(enhancedInstruction);
        applyState(node, state);
        renderPanel(node);
        queueMicrotask(() => node.__h3sEditor?.focus?.({ preventScroll: false }));
      },
    },
  });
  const labels = element("div", { className: "h3s-result-labels" }, result.labels.map((label) => (
    element("span", { className: "h3s-result-label", text: label, title: label })
  )));
  const analyzed = stateFromNode(node).prompt_options.analyze_images;
  const resultTitle = analyzed ? "Qwen-enhanced instruction" : "Compiled prompt";
  const children = [
    element("summary", {}, [
      element("span", { text: resultTitle }),
      element("span", { className: "h3s-result-actions" }, [edit, copy]),
    ]),
    labels,
    element("pre", { className: "h3s-result-prompt", text: enhancedInstruction }),
  ];
  if (analyzed && enhancedInstruction !== friendlyPrompt) {
    children.push(element("details", { className: "h3s-runtime-prompt" }, [
      element("summary", { text: "H3 runtime prompt" }),
      element("pre", { className: "h3s-result-prompt", text: friendlyPrompt }),
    ]));
  }
  if ((result.descriptions || []).some(Boolean)) {
    const records = result.descriptions
      .map((description, index) => `@Image${index + 1}: ${description || "No factual record"}`)
      .join("\n\n");
    children.push(element("details", { className: "h3s-runtime-prompt" }, [
      element("summary", { text: "What the detailed compiler received" }),
      element("pre", { className: "h3s-result-prompt", text: records }),
    ]));
  }
  return element("details", { className: "h3s-result", attrs: { open: "" } }, children);
}

async function queueDirectorWithSeed(node, seed) {
  const state = stateFromNode(node);
  state.generation = { ...state.generation, seed: Math.max(0, Math.trunc(seed)) };
  applyState(node, state);
  renderPanel(node);
  try {
    await app.queuePrompt(0);
  } catch (error) {
    app.extensionManager?.toast?.add?.({
      severity: "error",
      summary: "H3 Studio rerun failed",
      detail: String(error?.message || error),
      life: 6000,
    });
  }
}

function finalImageSection(node) {
  const result = node.__h3studioFinalImage;
  if (!result?.url) return null;
  const metadata = element("div", {
    className: "h3s-final-metadata",
    text: `Seed ${result.seed} · ${result.profile}`,
  });
  const image = element("img", {
    className: "h3s-final-image",
    src: result.url,
    alt: "Finished H3 Studio image",
    title: "Click to expand",
    on: {
      load: (event) => {
        result.width = event.target.naturalWidth;
        result.height = event.target.naturalHeight;
        metadata.textContent = `Seed ${result.seed} · ${result.width} × ${result.height} · ${result.profile}`;
      },
      click: (event) => {
        event.stopPropagation();
        openImageLightbox(result.url, metadata.textContent);
      },
    },
  });
  const different = () => {
    let seed = randomSeed();
    if (seed === result.seed) seed = (seed + 1) % Number.MAX_SAFE_INTEGER;
    queueDirectorWithSeed(node, seed);
  };
  const same = () => queueDirectorWithSeed(node, result.seed);
  const edit = () => {
    const state = stateFromNode(node);
    state.generation = { ...state.generation, seed: result.seed, seed_locked: true };
    applyState(node, state);
    renderPanel(node);
    queueMicrotask(() => node.__h3sEditor?.focus?.({ preventScroll: false }));
  };
  const actions = element("div", { className: "h3s-final-actions" }, [
    element("button", { className: "h3s-final-action", type: "button", text: "New seed", on: { click: different } }),
    element("button", { className: "h3s-final-action", type: "button", text: "Same seed", on: { click: same } }),
    element("button", {
      className: "h3s-final-action", type: "button", text: "Edit prompt · lock seed", on: { click: edit },
    }),
  ]);
  return section("Finished image", element("div", { className: "h3s-final-result" }, [image, metadata, actions]));
}

function controlRow(label, control) {
  return field(label, control);
}

function section(title, body, accessory = null, description = "") {
  const header = element("div", { className: "h3s-section-header" }, [
    element("span", { className: "h3s-section-title", text: title }),
    accessory,
  ]);
  const children = [header];
  if (description) children.push(element("p", { className: "h3s-section-description", text: description }));
  children.push(body);
  return element("section", { className: "h3s-section" }, children);
}

function samplingHelp(profile) {
  if (String(profile).startsWith("pdd_ref2va")) {
    if (String(profile).endsWith("600")) return "PDD checkpoint 600: Mamad8's alternate four-step REF2VA student. H3 Studio loads its matching LoRA and heads automatically and uses ComfyUI's bypass adapter path to avoid slow quantized-weight merging.";
    return "PDD checkpoint 900: Mamad8's later four-step REF2VA student and the recommended PDD starting point. H3 Studio loads its matching LoRA and heads automatically and uses ComfyUI's bypass adapter path to avoid slow quantized-weight merging.";
  }
  if (String(profile).startsWith("lightx")) {
    if (String(profile).includes("sa_solver")) return "LightX SA-Solver 4 (empirical): H3 Studio loads Kijai's resized rank-21 LightX v0.1 LoRA at the card's 0.75 strength. This is Kijai's tested ComfyUI recipe, not an official LightX guarantee. SA-Solver is stochastic and is not deterministic.";
    return "LightX ER-SDE 4 (empirical): H3 Studio loads Kijai's resized rank-21 LightX v0.1 LoRA at the card's 0.75 strength. This is Kijai's tested ComfyUI recipe, not an official LightX guarantee. Compare it with SA-Solver using the same prompt and seed.";
  }
  if (profile === "base_balanced_12") return "Base Balanced: native H3 at 12 RES steps. No LoRA or external package; faster than Base Quality with a smaller quality margin.";
  return "Base Quality: native H3 at 20 RES steps. No LoRA or external package; slowest sampling but the safest quality baseline.";
}

function generationSection(node, state, refresh) {
  const generation = state.generation;
  const update = (patch) => {
    state.generation = { ...state.generation, ...patch };
    applyState(node, state);
    refresh();
  };
  const mode = selectControl(generation.mode, [
    ["auto", "Auto · choose model"], ["text_to_image", "Text to image · FL2VA"],
    ["image_to_image", "Image to image · FL2VA anchor"],
    ["reference_edit", "Reference mix/edit · REF2VA"],
  ], "Generation mode", (value) => update({ mode: value }));
  const ratio = selectControl(generation.aspect_ratio, Object.keys(ASPECT_RATIOS), "Aspect ratio", (value) => update({ aspect_ratio: value }));
  const sampling = selectControl(generation.sampling_profile, SAMPLING_PROFILES, "Sampling speed", (value) => update({ sampling_profile: value }));
  sampling.title = samplingHelp(generation.sampling_profile);
  const frames = selectControl(generation.frame_profile, FRAME_PROFILES, "Temporal packet length", (value) => update({ frame_profile: value }));
  frames.title = generation.frame_profile === "image_vae_1"
    ? "Experimental image-only mode: sample one temporal latent and decode it with the optional Mamad8 Image VAE selected in H3 Studio Loader. Do not use this VAE for video."
    : "H3 normally benefits from a short temporal packet; the workflow selects one stable decoded still.";
  const seed = numberControl(generation.seed, { min: 0, max: Number.MAX_SAFE_INTEGER, step: 1 }, "Seed", (value) => update({ seed: Math.max(0, Math.trunc(value)) }));
  const random = iconButton("Randomize seed", "↻", () => update({ seed: randomSeed() }));
  const lock = iconButton(
    generation.seed_locked ? "Unlock seed after generation" : "Lock exact seed",
    generation.seed_locked ? "🔒" : "🔓",
    () => update({ seed_locked: !generation.seed_locked }),
    "h3s-seed-lock",
  );
  lock.setAttribute("aria-pressed", String(generation.seed_locked));
  const seedWrap = element("div", { className: "h3s-seed-row" }, [seed, random, lock]);
  const plan = planResolution(
    generation.aspect_ratio,
    generation.megapixels,
    generation.custom_width,
    generation.custom_height,
    generation.cap_native_resolution,
  );
  const preview = element("div", { className: "h3s-resolution-preview" }, [
    element("span", { text: `${plan.width} × ${plan.height}` }),
    element("span", { text: `${plan.actualMegapixels.toFixed(2)} MP${plan.capped ? " · conservative cap" : " · direct"}` }),
  ]);
  const megapixelValue = element("output", {
    className: "h3s-megapixel-value",
    text: formatMegapixels(generation.megapixels),
    attrs: { "aria-live": "polite" },
  });
  const megapixelSlider = rangeControl(
    generation.megapixels,
    { min: MIN_MEGAPIXELS, max: MAX_MEGAPIXELS, step: MEGAPIXEL_STEP },
    `Target megapixels, minimum ${formatMegapixels(MIN_MEGAPIXELS)}, maximum ${formatMegapixels(MAX_MEGAPIXELS)}`,
    (value) => {
      state.generation.megapixels = value;
      const next = planResolution(
        state.generation.aspect_ratio,
        value,
        state.generation.custom_width,
        state.generation.custom_height,
        state.generation.cap_native_resolution,
      );
      megapixelValue.textContent = formatMegapixels(value);
      preview.children[0].textContent = `${next.width} × ${next.height}`;
      preview.children[1].textContent = `${next.actualMegapixels.toFixed(2)} MP${next.capped ? " · conservative cap" : " · direct"}`;
      applyState(node, state);
    },
  );
  const megapixelControl = element("div", { className: "h3s-megapixel-control" }, [
    element("div", { className: "h3s-megapixel-top" }, [
      element("span", { text: formatMegapixels(MIN_MEGAPIXELS) }),
      megapixelValue,
      element("span", { text: formatMegapixels(MAX_MEGAPIXELS) }),
    ]),
    megapixelSlider,
  ]);
  const grid = element("div", { className: "h3s-grid" }, [
    controlRow("Mode", mode), controlRow("Aspect", ratio), controlRow("Target size", megapixelControl), controlRow("Seed", seedWrap),
    controlRow("Speed", sampling), controlRow("Frames", frames),
  ]);
  const sizeHelp = element("p", {
    className: "h3s-context-help",
    text: `Direct mode sends the aligned target canvas to H3 from ${formatMegapixels(MIN_MEGAPIXELS)} up to ${formatMegapixels(MAX_MEGAPIXELS)}. Higher resolution costs substantially more memory and is not a quality guarantee.`,
  });
  const help = element("p", { className: "h3s-context-help", text: samplingHelp(generation.sampling_profile) });
  const modeHelp = {
    auto: "Auto: no images uses FL2VA text-to-image; one image uses FL2VA as a first-frame anchor; two or more images use REF2VA as ordered references.",
    text_to_image: "Text to image · FL2VA: creates a new image from text. Uploaded references are intentionally ignored.",
    image_to_image: "Image to image · FL2VA anchor: transforms one source image while anchoring frame 0 to its canvas. Only Image 1 is used.",
    reference_edit: "Reference mix/edit · REF2VA: combines one or more independent references by their @Image roles, without treating any image as the locked canvas.",
  };
  const modeDescription = element("p", { className: "h3s-context-help", text: modeHelp[generation.mode] || modeHelp.auto });
  const validationMessage = validateGenerationContract(state);
  const validation = validationMessage
    ? element("p", { className: "h3s-validation-error", text: validationMessage, attrs: { role: "alert" } })
    : null;
  return section("Generation", element("div", { className: "h3s-section-stack" }, [grid, validation, modeDescription, sizeHelp, preview, help].filter(Boolean)));
}

function promptSection(node, state, refresh) {
  const update = (patch) => {
    state.prompt_options = { ...state.prompt_options, ...patch };
    applyState(node, state);
    refresh();
  };
  const options = state.prompt_options;
  const enhance = selectControl(options.enhance_mode, [
    ["off", "Keep my prompt"], ["single_prompt", "Clear one-line instruction"],
    ["compile_only", "Structured production brief"],
  ], "Prompt format", (value) => update({ enhance_mode: value }));
  const analyzerToggle = element("label", { className: "h3s-switch" }, [
    element("input", {
      type: "checkbox",
      checked: options.analyze_images === true,
      disabled: options.enhance_mode === "off",
      attrs: { "aria-label": "Analyze reference pixels with Qwen3-VL" },
      on: { change: (event) => update({ analyze_images: event.target.checked }) },
    }),
    element("span", { className: "h3s-switch-track" }),
    element("span", { className: "h3s-switch-label", text: "Analyze image pixels" }),
  ]);
  const analyzerResolution = selectControl(String(options.analyzer_resolution ?? 512), [
    ["384", "Fast · 384 px"],
    ["512", "Balanced · 512 px"],
    ["768", "Fine details · 768 px"],
    ["0", "Native · original pixels"],
  ], "Analyzer image detail", (value) => update({ analyzer_resolution: Number(value) }));
  analyzerResolution.disabled = options.analyze_images !== true || options.enhance_mode === "off";
  const directorToggle = element("label", { className: "h3s-switch" }, [
    element("input", {
      type: "checkbox",
      checked: options.deep_enhancement === true,
      disabled: options.analyze_images !== true || options.enhance_mode === "off",
      attrs: { "aria-label": "Build a fast deterministic detailed prompt" },
      on: { change: (event) => update({ deep_enhancement: event.target.checked }) },
    }),
    element("span", { className: "h3s-switch-track" }),
    element("span", { className: "h3s-switch-label", text: "Fast detailed expansion" }),
  ]);
  const writerInstruction = element("textarea", {
    className: "h3s-writer-instruction",
    value: options.system_instruction,
    placeholder: "Optional: extra creative direction for the detailed prompt compiler",
    attrs: { maxlength: "4000", "aria-label": "Optional prompt writer instruction" },
    on: {
      input: (event) => {
        state.prompt_options.system_instruction = event.target.value;
        applyState(node, state);
      },
    },
  });
  const promptStudio = element("details", { className: "h3s-prompt-studio" }, [
    element("summary", { text: "Prompt Studio · optional Qwen controls" }),
    element("div", { className: "h3s-section-stack" }, [
      element("p", {
        className: "h3s-context-help",
        text: node.__h3studioResult?.modelStatus || "Model status appears after the Director runs.",
      }),
      writerInstruction,
      element("p", {
        className: "h3s-context-help",
        text: "This guides the fast detailed compiler. Factual pixel analysis keeps its fixed source-only contract.",
      }),
    ]),
  ]);
  const adherenceValue = element("span", { className: "h3s-inline-value", text: `${Math.round(options.adherence * 100)}%` });
  const adherence = rangeControl(options.adherence, { min: 0, max: 1, step: 0.05 }, "Reference adherence", (value) => {
    adherenceValue.textContent = `${Math.round(value * 100)}%`;
    state.prompt_options.adherence = value;
    applyState(node, state);
  });
  const adherenceWrap = element("div", {}, [adherence, adherenceValue]);
  const explanations = {
    off: "Keeps your wording exactly and only converts @Image tags into H3's native reference syntax.",
    single_prompt: "Turns your request into one direct, easy-to-read H3 instruction with explicit image roles and preservation rules. It has no headings or line breaks and works especially well for simple edits and reference combinations.",
    compile_only: "Builds the four-section subject, summary, retention, and detailed-description format for complex art direction.",
  };
  const analyzerDetail = Number(options.analyzer_resolution) === 0
    ? "the original reference resolution (slowest, maximum fidelity)"
    : `analysis copies up to ${options.analyzer_resolution || 512}px`;
  const analyzerHelp = options.analyze_images
    ? `Qwen3-VL inspects ${analyzerDetail}, improves the instruction, and supplies source-only roles and descriptions. H3 always receives the untouched originals. It reruns only when the prompt, references, or analyzer detail changes.`
    : "Pixel analysis is off; roles come from your wording and manual reference controls.";
  const missingOrdinals = missingReferenceOrdinals(state);
  const missingLabels = missingOrdinals.map((ordinal) => `@Image${ordinal}`);
  const referenceNotice = missingOrdinals.length
    ? element("div", { className: "h3s-validation-notice", attrs: { role: "alert", "aria-live": "polite" } }, [
      element("div", { className: "h3s-validation-notice-copy" }, [
        element("strong", { text: `${missingLabels.join(", ")} ${missingOrdinals.length === 1 ? "is" : "are"} not connected` }),
        element("span", { text: "Reconnect or enable the matching image card, or remove only the stale mention from your prompt." }),
      ]),
      element("button", {
        className: "h3s-validation-fix",
        type: "button",
        text: missingOrdinals.length === 1 ? `Remove ${missingLabels[0]}` : "Remove stale mentions",
        attrs: { "aria-label": `Remove ${missingLabels.join(", ")} from prompt` },
        on: {
          click: () => {
            const fixedPrompt = removeReferenceMentions(state.prompt, missingOrdinals);
            state.prompt = fixedPrompt;
            setWidget(node, "prompt", fixedPrompt);
            node.__h3sDomWidget?.setValue?.(fixedPrompt);
            applyState(node, state);
            app.extensionManager?.toast?.add?.({
              severity: "success",
              summary: "H3 Studio prompt fixed",
              detail: `${missingLabels.join(", ")} removed. Review the prompt, then queue again.`,
              life: 4500,
            });
            refresh();
          },
        },
      }),
    ])
    : null;
  const body = element("div", { className: "h3s-section-stack" }, [
    referenceNotice,
    element("div", { className: "h3s-grid" }, [
      controlRow("Prompt format", enhance), controlRow("Image understanding", analyzerToggle),
      controlRow("Analyzer detail", analyzerResolution), controlRow("Prompt director", directorToggle),
      controlRow("Reference priority", adherenceWrap),
    ]),
    element("p", { className: "h3s-context-help", text: `${explanations[options.enhance_mode]} ${analyzerHelp} ${options.deep_enhancement ? "Fast detailed expansion is ON: the deterministic compiler builds the full production direction without loading a second language model." : "Detailed expansion is OFF: pixel analysis still describes and assigns references, but the generated instruction stays intentionally short (about 40-90 words)."} Reference priority controls how strongly the written prompt tells H3 to preserve reference details; it is not a LoRA strength.` }),
    promptStudio,
  ]);
  return section("Direction", body, null, "Choose how H3 Studio prepares your words before Qwen3-VL encodes them for H3.");
}

function referenceCard(node, state, reference, index, refresh) {
  const link = reference.source_node_id == null ? null : normalizedLinks(node).find(
    (candidate) => Number(candidate.source_id) === Number(reference.source_node_id)
      && Number(candidate.source_slot) === Number(reference.source_slot || 0),
  );
  const source = sourceNode(link);
  const preview = reference.storage_name
    ? previewUrlForStorage(reference.storage_name)
    : sourcePreview(source) || reference.thumbnail;
  const fullImage = reference.storage_name
    ? mediaUrlForStorage(reference.storage_name)
    : sourceMedia(source) || fullMediaUrl(reference.thumbnail || preview);
  const ratio = Number(reference.width) > 0 && Number(reference.height) > 0
    ? Number(reference.width) / Number(reference.height)
    : null;
  const thumb = element("div", { className: "h3s-reference-thumb" }, [
    preview ? element("img", {
      src: preview,
      alt: `Preview of @Image${index + 1}`,
      title: "Click to expand",
      on: {
        load: (event) => {
          const naturalRatio = event.target.naturalWidth / Math.max(1, event.target.naturalHeight);
          event.target.parentElement?.style.setProperty("--h3s-reference-ratio", String(ratio || naturalRatio));
        },
        click: (event) => {
          event.stopPropagation();
          openImageLightbox(fullImage, `${reference.filename} · @Image${index + 1}`);
        },
      },
    }) : element("span", { className: "h3s-thumb-placeholder", text: "IMG" }),
    element("span", { className: "h3s-reference-index", text: `@Image${index + 1}` }),
  ]);
  if (ratio) thumb.style.setProperty("--h3s-reference-ratio", String(ratio));
  const mutate = (patch) => {
    state.references[index] = { ...state.references[index], ...patch };
    if (node.__h3studioAutoChanges) delete node.__h3studioAutoChanges[index];
    applyState(node, state);
  };
  const move = (delta) => {
    const next = index + delta;
    if (next < 0 || next >= state.references.length) return;
    const reordered = [...state.references];
    [reordered[index], reordered[next]] = [reordered[next], reordered[index]];
    state.references = reordered.map((referenceItem, ordinal) => ({ ...referenceItem, ordinal: ordinal + 1 }));
    writeLinksFromReferences(node, state.references);
    applyState(node, state);
    notifyReferenceChange(node);
    refresh();
  };
  const remove = () => {
    if (reference.source_node_id != null) {
      writeLinks(node, normalizedLinks(node).filter((candidate) => linkKey(candidate) !== linkKey(link)));
    }
    state.references.splice(index, 1);
    state.references = state.references.map((referenceItem, ordinal) => ({ ...referenceItem, ordinal: ordinal + 1 }));
    applyState(node, state);
    notifyReferenceChange(node);
    refresh();
  };
  const actions = element("div", { className: "h3s-reference-actions" }, [
    iconButton("Move image up", "↑", () => move(-1)),
    iconButton("Move image down", "↓", () => move(1)),
    iconButton("Remove image", "×", remove, "h3s-danger"),
  ]);
  actions.children[0].disabled = index === 0;
  actions.children[1].disabled = index === state.references.length - 1;
  const title = element("div", { className: "h3s-reference-top" }, [
    element("span", { className: "h3s-reference-name", text: reference.filename, title: reference.filename }), actions,
  ]);
  const sourceDetails = Number(reference.width) > 0 && Number(reference.height) > 0
    ? element("div", { className: "h3s-reference-source", text: `${reference.width} × ${reference.height} · ${(reference.width / reference.height).toFixed(3)}:1` })
    : null;
  const role = selectControl(reference.role, ROLES, `Role for Image ${index + 1}`, (value) => mutate({ role: value, role_auto: value === "auto" }));
  const retentionHelp = {
    attribute_transfer: "Transfer only the assigned trait, such as clothing or style; do not copy unrelated source content.",
    fully_preserved: "Keep the assigned identity or source details as faithfully as possible; change only what the prompt requests.",
    partially_preserved: "Keep the recognizable core while allowing the new scene, pose, framing, or edit to adapt it.",
    reference_only: "Use the image as loose guidance; exact identity and details do not need to be copied.",
  };
  const retention = selectControl(reference.retention, RETENTION, retentionHelp[reference.retention], (value) => mutate({ retention: value, retention_auto: false }));
  const description = element("textarea", {
    className: "h3s-reference-description", value: reference.description,
    placeholder: "What this image defines…", attrs: { "aria-label": `Description for Image ${index + 1}` },
    on: { change: (event) => mutate({ description: event.target.value, description_auto: false }) },
  });
  const controls = element("div", { className: "h3s-reference-controls" }, [role, retention]);
  const retentionHint = element("div", { className: "h3s-reference-help", text: retentionHelp[reference.retention] });
  const changedNow = node.__h3studioAutoChanges?.[index];
  const autoChange = changedNow || (
    (reference.role_auto || reference.retention_auto) && reference.role !== "auto"
      ? { role: reference.role, retention: reference.retention }
      : null
  );
  const roleHint = autoChange
    ? element("div", { className: "h3s-auto-role", text: `${changedNow?.analyzed ? "Image analyzed" : changedNow ? "Prompt updated" : "Prompt-managed"} · ${autoChange.role} · ${autoChange.retention}` })
    : null;
  return element("article", { className: `h3s-reference-card${autoChange ? " h3s-reference-card-auto" : ""}` }, [
    thumb,
    element("div", { className: "h3s-reference-body" }, [title, sourceDetails, controls, roleHint, retentionHint, description].filter(Boolean)),
  ]);
}

async function addImages(node, state, refresh, providedFiles = null) {
  const capacity = MAX_REFERENCES - state.references.length;
  if (capacity <= 0 || node.__h3studioUploading) return;
  const selected = providedFiles || await chooseImageFiles({ multiple: true });
  const files = [...selected].slice(0, capacity);
  if (!files.length) return;
  node.__h3studioUploading = true;
  node.__h3studioUploadError = "";
  node.__h3studioUploadLabel = `Uploading 0/${files.length}`;
  refresh();
  try {
    const uploadedFiles = await uploadImages(api, files, {
      concurrency: 3,
      onProgress: (completed, total) => {
        node.__h3studioUploadLabel = `Uploading ${completed}/${total}`;
        refresh();
      },
    });
    uploadedFiles.forEach((uploaded, index) => {
      state.references.push({
        id: `upload_${globalThis.crypto?.randomUUID?.() || `${Date.now()}_${index}`}`,
        filename: uploaded.filename,
        storage_name: uploaded.storage_name,
        thumbnail: previewUrlForStorage(uploaded.storage_name),
        ordinal: state.references.length + 1,
        role: "auto",
        retention: "attribute_transfer",
        role_auto: true,
        retention_auto: true,
        description: "",
        description_auto: true,
        enabled: true,
        source_node_id: null,
        source_slot: 0,
      });
    });
    applyState(node, state);
    notifyReferenceChange(node);
  } catch (error) {
    node.__h3studioUploadError = error instanceof Error ? error.message : String(error);
  } finally {
    node.__h3studioUploading = false;
    node.__h3studioUploadLabel = "";
    refresh();
  }
}

function referencesSection(node, state, refresh) {
  const list = element("div", {
    className: "h3s-reference-list",
    attrs: { "aria-label": "Reference images; drop one or more image files here" },
    on: {
      dragenter: (event) => { event.preventDefault(); event.stopPropagation(); list.classList.add("is-dragging"); },
      dragover: (event) => { event.preventDefault(); event.stopPropagation(); if (event.dataTransfer) event.dataTransfer.dropEffect = "copy"; },
      dragleave: (event) => { event.preventDefault(); if (!list.contains(event.relatedTarget)) list.classList.remove("is-dragging"); },
      drop: (event) => {
        event.preventDefault();
        event.stopPropagation();
        list.classList.remove("is-dragging");
        const files = imageFilesFromTransfer(event.dataTransfer);
        if (files.length) addImages(node, state, refresh, files);
      },
    },
  });
  if (!state.references.length) {
    list.append(element("div", { className: "h3s-empty" }, [
      element("strong", { text: "Text-to-image ready" }),
      element("span", { text: "Drop images here or add several at once. They become @Image1 through @Image9." }),
    ]));
  } else {
    state.references.forEach((reference, index) => list.append(referenceCard(node, state, reference, index, refresh)));
  }
  if (node.__h3studioUploadError) {
    list.prepend(element("div", { className: "h3s-upload-error", text: node.__h3studioUploadError, attrs: { role: "alert" } }));
  }
  const addButton = element("button", {
    className: "h3s-add-image", type: "button",
    disabled: state.references.length >= MAX_REFERENCES || Boolean(node.__h3studioUploading),
    text: node.__h3studioUploading ? node.__h3studioUploadLabel || "Uploading…" : "+ Add images",
    attrs: { "aria-label": "Upload reference images" },
    on: { click: () => addImages(node, state, refresh) },
  });
  const accessory = element("div", { className: "h3s-reference-heading-actions" }, [
    element("span", { className: "h3s-status-pill", text: `${state.references.length}/${MAX_REFERENCES}` }),
    addButton,
  ]);
  const body = element("div", { className: "h3s-section-stack" }, [
    element("p", {
      className: "h3s-context-help",
      text: "Visual analysis uses the full Qwen3-VL model selected in H3 Studio Loader to inspect the actual pixels, assign each @Image role, and fill these descriptions. Manual descriptions stay under your control.",
    }),
    list,
  ]);
  return section("References", body, accessory);
}

function advancedSection(node, state, refresh) {
  const content = element("div", { className: "h3s-advanced-content h3s-section-stack" });
  content.hidden = !state.ui.advanced_open;
  const update = (generationPatch = {}, promptPatch = {}) => {
    state.generation = { ...state.generation, ...generationPatch };
    state.prompt_options = { ...state.prompt_options, ...promptPatch };
    applyState(node, state);
    refresh();
  };
  const resolutionMode = selectControl(
    state.generation.cap_native_resolution ? "conservative" : "direct",
    [["direct", "Direct · honor target"], ["conservative", "Conservative · ~1 MP cap"]],
    "Resolution planning mode",
    (value) => update({ cap_native_resolution: value === "conservative" }),
  );
  content.append(element("div", { className: "h3s-grid" }, [
    controlRow("Model route", selectControl(state.generation.route, [
      ["auto", "Auto · choose for me"], ["fl2va", "Force FL2VA"], ["ref2va", "Force REF2VA"],
    ], "Conditioning route", (value) => update({ route: value }))),
    controlRow("Resolution mode", resolutionMode),
  ]));
  content.append(element("p", { className: "h3s-context-help", text: "Direct mode honors multi-megapixel targets. Conservative mode intentionally applies the older ~1 MP area cap. Model route normally follows Mode; force a route only for controlled comparisons." }));
  const toggle = element("button", {
    className: "h3s-advanced-toggle", type: "button", attrs: { "aria-expanded": String(state.ui.advanced_open) },
    on: { click: () => { state.ui.advanced_open = !state.ui.advanced_open; applyState(node, state); refresh(); } },
  }, [element("span", { text: "Advanced controls" }), element("span", { text: state.ui.advanced_open ? "−" : "+" })]);
  return element("section", { className: "h3s-section" }, [toggle, content]);
}

function renderPanel(node) {
  const root = node.__h3studioPanel;
  if (!root) return;
  const state = applyState(node, stateFromNode(node), false);
  root.replaceChildren();
  const refresh = () => renderPanel(node);
  const resolvedMode = state.references.length ? "Reference ready" : "T2I ready";
  const children = [
    element("header", { className: "h3s-studio-header" }, [
      element("div", { className: "h3s-studio-brand" }, [element("span", { className: "h3s-studio-mark" }), element("span", { className: "h3s-studio-title", text: "MiniMax H3 Studio" })]),
      element("span", { className: "h3s-status-pill", text: resolvedMode }),
    ]),
    node.__h3studioStateError ? element("div", {
      className: "h3s-state-warning",
      text: `${node.__h3studioStateError} The original value was preserved for recovery.`,
    }) : null,
    generationSection(node, state, refresh),
    promptSection(node, state, refresh),
    finalImageSection(node),
    resultsSection(node),
    referencesSection(node, state, refresh),
    advancedSection(node, state, refresh),
  ].filter(Boolean);
  root.append(...children);
  node.__h3studioLinkSignature = linkSignature(node);
}

api.addEventListener("executed", ({ detail }) => {
  const targetId = detail?.node;
  const outputNode = app.graph?.getNodeById?.(Number(targetId));
  if (!outputNode || !["PreviewImage", "H3StudioSaveImage"].includes(outputNode.comfyClass)) return;
  const item = detail?.output?.images?.[0];
  const url = executedImageUrl(item);
  if (!url) return;
  for (const node of app.graph?._nodes || []) {
    if (node.comfyClass !== TARGET || !isNodeDownstream(app.graph?.links, node.id, targetId)) continue;
    const state = stateFromNode(node);
    node.__h3studioFinalImage = {
      url,
      seed: state.generation.seed,
      profile: state.generation.sampling_profile,
      promptId: promptId(detail),
    };
    queueMicrotask(() => renderPanel(node));
  }
});

function installPanel(node) {
  if (node.__h3studioPanelInstalled || typeof node.addDOMWidget !== "function") return;
  node.__h3studioPanelInstalled = true;
  installTheme();
  enforceNativeWidgetVisibility(node);
  const root = element("div", { className: "h3s-studio-panel", attrs: { role: "group", "aria-label": "MiniMax H3 Studio controls" } });
  node.__h3studioPanel = root;
  const panelWidget = node.addDOMWidget("h3studio_controls", "h3studio_controls", root, {
    serialize: false,
    hideOnZoom: false,
    getValue: () => undefined,
  });
  // The widget height must not be derived from the total node height. ComfyUI
  // calculates that total from computeSize(), so coupling the two produces a
  // positive resize-feedback loop and makes the node grow forever.
  panelWidget.computeSize = studioPanelSize;
  panelWidget.computedHeight = STUDIO_PANEL_HEIGHT;

  const stateWidget = widget(node, "studio_state");
  if (stateWidget && !stateWidget.__h3studioQueueValidation) {
    stateWidget.__h3studioQueueValidation = true;
    const originalBeforeQueued = stateWidget.beforeQueued;
    stateWidget.beforeQueued = async function h3studioBeforeQueued() {
      const result = await originalBeforeQueued?.apply(this, arguments);
      const state = stateFromNode(node);
      const missingOrdinals = missingReferenceOrdinals(state);
      const missingLabels = missingOrdinals.map((ordinal) => `@Image${ordinal}`);
      const fixLabel = missingOrdinals.length === 1 ? `Remove ${missingLabels[0]}` : "Remove stale mentions";
      const message = missingOrdinals.length
        ? `${missingLabels.join(", ")} ${missingOrdinals.length === 1 ? "has" : "have"} no enabled image card. Reconnect the image or use ${fixLabel} in Direction.`
        : validateGenerationContract(state);
      if (message) {
        if (missingOrdinals.length) renderPanel(node);
        app.extensionManager?.toast?.add?.({
          severity: "error",
          summary: "H3 Studio configuration",
          detail: message,
          life: 7000,
        });
        throw new Error(message);
      }
      return result;
    };
  }

  node.__h3studioBeforeSerialize = function h3studioBeforeSerialize() {
    this.__h3studioSerializedState = applyState(this, stateFromNode(this), false);
  };
  node.__h3studioAfterSerialize = function h3studioAfterSerialize(data) {
    const state = this.__h3studioSerializedState || stateFromNode(this);
    this.__h3studioSerializedState = null;
    if (data) {
      data.properties ||= {};
      data.properties[STATE_PROPERTY] = serializeState(state);
      data.properties[LINKS_PROPERTY] = normalizedLinks(this);
      if (this.properties?.[STATE_RECOVERY_PROPERTY]) {
        data.properties[STATE_RECOVERY_PROPERTY] = this.properties[STATE_RECOVERY_PROPERTY];
      }
    }
  };
  node.__h3studioConfigured = function h3studioConfigured() {
    queueMicrotask(() => renderPanel(this));
  };
  const originalExecuted = node.onExecuted;
  node.onExecuted = function h3studioExecuted(message) {
    const result = originalExecuted?.apply(this, arguments);
    const roles = executionValue(message, "reference_roles");
    const retentions = executionValue(message, "reference_retentions");
    const descriptions = executionValue(message, "reference_descriptions");
    const { state, changes: autoChanges } = applyReferenceInferences(
      stateFromNode(this), roles, retentions, descriptions,
    );
    applyState(this, state, false);
    this.__h3studioAutoChanges = autoChanges;
    this.__h3studioResult = {
      prompt: executionValue(message, "compiled_prompt")[0] || "",
      enhancedPrompt: executionValue(message, "enhanced_instruction")[0] || "",
      labels: executionValue(message, "reference_labels"),
      roles,
      retentions,
      descriptions,
      modelStatus: executionValue(message, "analyzer_status")[0] || "",
      diagnostics: executionValue(message, "diagnostics")[0] || "",
    };
    queueMicrotask(() => renderPanel(this));
    // Advance only when the entire prompt succeeds. Director executes before
    // sampling, so changing here would expose a seed that has not generated yet.
    queueSeedAdvance(this);
    return result;
  };
  node.__h3studioConnectionsChanged = function h3studioConnectionsChanged() {
    queueMicrotask(() => renderPanel(this));
  };
  node.__h3studioDrawForeground = function h3studioDrawForeground() {
    enforceNativeWidgetVisibility(this);
    const signature = linkSignature(this);
    if (signature !== this.__h3studioLinkSignature && !this.__h3studioRenderQueued) {
      this.__h3studioRenderQueued = true;
      queueMicrotask(() => {
        this.__h3studioRenderQueued = false;
        renderPanel(this);
      });
    }
  };
  // Reset any runaway height already serialized into an existing workflow,
  // while preserving a deliberately wider node.
  node.size = initialStudioNodeSize(node.size);
  renderPanel(node);
}

app.registerExtension({
  name: "H3Studio.Controls",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== TARGET) return;
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function h3studioCreated() {
      const result = originalCreated?.apply(this, arguments);
      queueMicrotask(() => installPanel(this));
      return result;
    };
  },
});

export { applyState, linkSignature, normalizedLinks, stateFromNode };
