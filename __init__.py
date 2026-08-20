"""ComfyUI entry point for MiniMax H3 Studio."""

# Pytest imports a repository-level ``__init__.py`` as a standalone collection
# module. ComfyUI imports it as a real package, where relative imports are valid.
if __package__:
    from .h3studio.extension import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
    from .h3studio.single_frame_vae_500k import install as install_single_frame_vae_500k
    from .h3studio.smart_benchmark_compat import install as install_smart_benchmark_compat
    # Install after extension registration so the runtime policies see the
    # completed analyzer/writer and Smart Benchmark schemas.
    from .h3studio.prompt_prep_residency_fast import install as install_prompt_prep_residency_fast
    from .h3studio.consolidated_integrity_fix import install as install_consolidated_integrity_fix
    from .h3studio.post_merge_fixes import install as install_post_merge_fixes
    from .h3studio.history_fast_restore import register_fast_history_restore_route

    # Register current single-frame VAE choices and safe 500K decode defaults.
    install_single_frame_vae_500k()
    # Accept stale alpha Smart Benchmark values before ComfyUI validation.
    install_smart_benchmark_compat()
    # Keep the Qwen3.5 helper warm for one Director pass, then hand VRAM back to H3.
    install_prompt_prep_residency_fast()
    # Apply prompt/reference/PNG/preview integrity fixes after runtime registration.
    install_consolidated_integrity_fix()
    # Fill the one-reference semantic resize gap and make automatic roles prompt-aware.
    install_post_merge_fixes()
    # Restore History from its already-indexed SQLite state instead of re-reading
    # the full PNG on every click. PNG metadata remains the fallback source.
    register_fast_history_restore_route()
else:  # pragma: no cover - collection shim, not the ComfyUI execution path
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
