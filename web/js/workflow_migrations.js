export const BENCHMARK_DEFAULTS = Object.freeze({
    comparison_kind: "Sampling profiles x resolution",
    profiles: "base_quality_20, lightx_v1_fl2v_8",
    megapixels: "0.40, 1.00, 2.00",
    repeats: 1,
    seed_strategy: "Same seed for all - fair comparison",
    seed_step: 1,
    grid_cell_size: 640,
    max_generations: 24,
    allow_large_matrix: false,
    include_reference_context: true,
    include_original_prompt: true,
    live_cell_previews: true,
});

export const BENCHMARK_KINDS = Object.freeze([
    "Sampling profiles x resolution",
    "VAE decode - same T=1 latent",
]);

export const BENCHMARK_SEED_STRATEGIES = Object.freeze([
    "Same seed for all - fair comparison",
    "New seed each row - paired comparison",
    "New seed every image - diversity sweep",
]);

const LOADER_PROMPT_WRITER_FALLBACK = "Same as image analyzer";

function widgetByName(node, name) {
    return (node?.widgets || []).find((widget) => String(widget?.name || "") === name) || null;
}

function comboValues(widget) {
    const source = widget?.options?.values;
    try {
        const values = typeof source === "function" ? source(widget) : source;
        return Array.isArray(values) ? values.map(String) : [];
    } catch {
        return [];
    }
}

function assign(widget, value) {
    if (!widget || Object.is(widget.value, value)) return false;
    widget.value = value;
    try {
        widget.callback?.(value);
    } catch {
        // Migration must never make workflow loading fail.
    }
    return true;
}

function validInteger(value, min, max) {
    return Number.isInteger(value) && value >= min && value <= max;
}

export function migrateLoaderWidgets(node) {
    const promptWriter = widgetByName(node, "prompt_writer");
    if (!promptWriter) return false;

    const current = String(promptWriter.value ?? "");
    const allowed = comboValues(promptWriter);
    if (current && (!allowed.length || allowed.includes(current))) return false;

    const fallback = allowed.includes(LOADER_PROMPT_WRITER_FALLBACK)
        ? LOADER_PROMPT_WRITER_FALLBACK
        : allowed[0] || LOADER_PROMPT_WRITER_FALLBACK;
    return assign(promptWriter, fallback);
}

export function migrateBenchmarkWidgets(node) {
    let changed = false;
    const get = (name) => widgetByName(node, name);

    const comparisonKind = get("comparison_kind");
    if (!BENCHMARK_KINDS.includes(String(comparisonKind?.value ?? ""))) {
        changed = assign(comparisonKind, BENCHMARK_DEFAULTS.comparison_kind) || changed;
    }

    const profiles = get("profiles");
    if (typeof profiles?.value !== "string" || !profiles.value.trim()) {
        changed = assign(profiles, BENCHMARK_DEFAULTS.profiles) || changed;
    }

    const megapixels = get("megapixels");
    if (typeof megapixels?.value !== "string" || !megapixels.value.trim()) {
        changed = assign(megapixels, BENCHMARK_DEFAULTS.megapixels) || changed;
    }

    const repeats = get("repeats");
    if (!validInteger(repeats?.value, 1, 16)) {
        changed = assign(repeats, BENCHMARK_DEFAULTS.repeats) || changed;
    }

    const seedStrategy = get("seed_strategy");
    if (!BENCHMARK_SEED_STRATEGIES.includes(String(seedStrategy?.value ?? ""))) {
        changed = assign(seedStrategy, BENCHMARK_DEFAULTS.seed_strategy) || changed;
    }

    const seedStep = get("seed_step");
    if (!validInteger(seedStep?.value, 1, 1_000_000)) {
        changed = assign(seedStep, BENCHMARK_DEFAULTS.seed_step) || changed;
    }

    const gridCellSize = get("grid_cell_size");
    if (!validInteger(gridCellSize?.value, 320, 1024)) {
        changed = assign(gridCellSize, BENCHMARK_DEFAULTS.grid_cell_size) || changed;
    }

    const maxGenerations = get("max_generations");
    if (!validInteger(maxGenerations?.value, 1, 128)) {
        changed = assign(maxGenerations, BENCHMARK_DEFAULTS.max_generations) || changed;
    }

    for (const name of [
        "allow_large_matrix",
        "include_reference_context",
        "include_original_prompt",
        "live_cell_previews",
    ]) {
        const widget = get(name);
        if (typeof widget?.value !== "boolean") {
            changed = assign(widget, BENCHMARK_DEFAULTS[name]) || changed;
        }
    }

    return changed;
}
