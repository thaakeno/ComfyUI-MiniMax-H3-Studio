"""ComfyUI entry point for MiniMax H3 Studio."""

# The v2 registration path is intentionally unique so a stale cached
# h3studio.extension module cannot revive an older runtime implementation.
if __package__:
    from .h3studio.extension_v2 import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
else:  # pragma: no cover - collection shim, not the ComfyUI execution path
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
