"""ComfyUI entry point for MiniMax H3 Studio."""

# v3 restores the proven stable sampler/decode lifecycle and keeps TAEH3 off
# the GPU so preview work cannot steal DynamicVRAM residency from H3.
if __package__:
    from .h3studio.extension_v3 import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
else:  # pragma: no cover - collection shim, not the ComfyUI execution path
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
