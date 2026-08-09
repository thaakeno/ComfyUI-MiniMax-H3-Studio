"""MiniMax H3 Studio runtime package.

Pure modules in this package deliberately avoid importing ComfyUI so they can be
tested in a normal Python environment. Only :mod:`h3studio.extension` and the
modules under :mod:`h3studio.nodes` cross the ComfyUI boundary.
"""

from .constants import STATE_SCHEMA_VERSION, VERSION
from .state import StudioState

__all__ = ["STATE_SCHEMA_VERSION", "StudioState", "VERSION"]
