"""Root entry point so ComfyUI finds the Open Optics nodes.

ComfyUI loads a custom-node folder with importlib under its own module name
and does not put the folder on sys.path, so the absolute imports inside the
pack (`open_optics`, `open_optics_nodes`) would fail. Appending this folder
makes them resolve. It is appended, not prepended, so the folder's other
top-level names (tests, bench, scripts) never shadow another package.
"""

import os
import sys

_PACK_DIR = os.path.dirname(os.path.abspath(__file__))
if _PACK_DIR not in sys.path:
    sys.path.append(_PACK_DIR)

from open_optics_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS  # noqa: E402

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
