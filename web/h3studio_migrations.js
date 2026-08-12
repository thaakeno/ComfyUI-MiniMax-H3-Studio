import { app } from "../../scripts/app.js";
import { migrateBenchmarkWidgets, migrateLoaderWidgets } from "./js/workflow_migrations.js";

const LOADER_CLASS = "H3StudioLoader";
const BENCHMARK_CLASS = "H3StudioABComparison";

function installMigration(nodeType, migrate) {
    if (nodeType.prototype.__h3studioWorkflowMigrationInstalled) return;
    nodeType.prototype.__h3studioWorkflowMigrationInstalled = true;

    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function onNodeCreatedH3StudioMigration() {
        const result = originalCreated?.apply(this, arguments);
        migrate(this);
        return result;
    };

    const originalConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function onConfigureH3StudioMigration(info) {
        const result = originalConfigure?.apply(this, arguments);
        const changed = migrate(this);
        if (changed) {
            this.properties ||= {};
            this.properties.h3studio_widget_schema_repaired = "2026-08-12";
            this.setDirtyCanvas?.(true, true);
            console.info(`[H3 Studio] Repaired stale widget schema for ${this.title || this.type || "node"}.`);
        }
        return result;
    };
}

app.registerExtension({
    name: "H3Studio.WorkflowMigrations",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData?.name === LOADER_CLASS) installMigration(nodeType, migrateLoaderWidgets);
        if (nodeData?.name === BENCHMARK_CLASS) installMigration(nodeType, migrateBenchmarkWidgets);
    },
});
