"""UI-only model setup companion for the maintained H3 Studio workflow."""

from __future__ import annotations


class H3StudioModelSetup:
    """Frontend-driven model setup panel.

    The node intentionally has no execution outputs. Its DOM UI is provided by
    ``web/h3_model_setup.js`` and talks to Universal Asset Downloader only when
    that companion node is installed.
    """

    CATEGORY = "H3 Studio"
    RETURN_TYPES = ()
    FUNCTION = "noop"
    DESCRIPTION = (
        "Verify and install the maintained MiniMax H3 model set. "
        "Uses Universal Asset Downloader when available."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    def noop(self):
        return ()


NODE_CLASS_MAPPINGS = {"H3StudioModelSetup": H3StudioModelSetup}
NODE_DISPLAY_NAME_MAPPINGS = {"H3StudioModelSetup": "H3 Studio · Model Setup"}
