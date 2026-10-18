"""Open Optics ComfyUI node pack."""

from .focal_crop import OpenOptics_FocalCrop
from .vignette import OpenOptics_Vignette

NODE_CLASS_MAPPINGS = {
    "OpenOptics_FocalCrop": OpenOptics_FocalCrop,
    "OpenOptics_Vignette": OpenOptics_Vignette,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "OpenOptics_FocalCrop": "Open Optics: Focal Crop",
    "OpenOptics_Vignette": "Open Optics: Vignette",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
