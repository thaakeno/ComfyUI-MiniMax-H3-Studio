# Execution contract

Treat `plans.md` as authoritative and proceed milestone by milestone without pausing for routine confirmation.

Validate after every milestone and commit only a coherent checkpoint. Keep unrelated user files untouched. Never rewrite history, force-push, or delete recovery points.

Prefer small modules with explicit contracts over large catch-all files. Add tests alongside behavior. When a defect survives two plausible fixes, stop patching and measure the failing path.

Keep documentation synchronized with actual behavior. Do not document planned features as shipped. Mark all CUDA, VRAM and image-quality claims unverified until they are exercised in Alier's Lightning.ai ComfyUI environment.

Completion requires all locally available tests passing, deterministic workflow generation, a clean working tree, meaningful commit history, a private GitHub repository, and a successful push of `main`.

## Completion checkpoint

All repository implementation milestones are complete. The source contains 9,436 custom-node runtime lines, a 2,103-line maintained workflow, a 718-line reusable subgraph, release automation, and an exact Lightning.ai smoke-test handoff. CUDA generation remains deliberately unclaimed until that handoff is run in the target workspace.
