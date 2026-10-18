"""Open Optics ComfyUI node pack."""

from .focal_crop import OpenOptics_FocalCrop

NODE_CLASS_MAPPINGS = {
    "OpenOptics_FocalCrop": OpenOptics_FocalCrop,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "OpenOptics_FocalCrop": "Open Optics: Focal Crop",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
