import assert from "node:assert/strict";
import test from "node:test";

import {
    BENCHMARK_DEFAULTS,
    migrateBenchmarkWidgets,
    migrateLoaderWidgets,
} from "../../web/js/workflow_migrations.js";

function widget(name, value, values = undefined) {
    return { name, value, options: values ? { values } : {} };
}

test("loader repairs stale analyzer value that drifted into prompt_writer", () => {
    const node = {
        widgets: [
            widget("image_analyzer", "Auto · Qwen3-VL 4B"),
            widget("prompt_writer", "Auto · Qwen3-VL 4B", [
                "Same as image analyzer",
                "Auto · Qwen3-VL 4B writer",
            ]),
        ],
    };

    assert.equal(migrateLoaderWidgets(node), true);
    assert.equal(node.widgets[1].value, "Same as image analyzer");
});

test("benchmark repairs positional drift without overwriting valid fields", () => {
    const node = {
        widgets: [
            widget("comparison_kind", "Sampling profiles x resolution"),
            widget("profiles", "base_quality_20, lightx_v1_fl2v_8"),
            widget("megapixels", "0.40, 1.00"),
            widget("repeats", "Same seed for all - fair comparison"),
            widget("seed_strategy", 1),
            widget("seed_step", 640),
            widget("grid_cell_size", 24),
            widget("max_generations", false),
            widget("allow_large_matrix", true),
            widget("include_reference_context", true),
            widget("include_original_prompt", true),
            widget("live_cell_previews", true),
        ],
    };

    assert.equal(migrateBenchmarkWidgets(node), true);
    assert.equal(node.widgets[1].value, "base_quality_20, lightx_v1_fl2v_8");
    assert.equal(node.widgets[2].value, "0.40, 1.00");
    assert.equal(node.widgets[3].value, BENCHMARK_DEFAULTS.repeats);
    assert.equal(node.widgets[4].value, BENCHMARK_DEFAULTS.seed_strategy);
    assert.equal(node.widgets[6].value, BENCHMARK_DEFAULTS.grid_cell_size);
    assert.equal(node.widgets[7].value, BENCHMARK_DEFAULTS.max_generations);
});
