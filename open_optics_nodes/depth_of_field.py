"""Depth of Field node for the Open Optics pack (CPU torch tensors)."""

import torch

from open_optics_nodes import common
from open_optics_nodes.dof_math import composite_layers, coc_radius_map

_LAYERS = {"draft": 4, "normal": 8}


class OpenOptics_DepthOfField:
    """Blur an image by layered depth of field from real lens parameters."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "focal_mm": ("FLOAT", {"default": 50.0, "min": 1.0, "max": 1000.0, "step": 0.1}),
                "f_number": ("FLOAT", {"default": 2.8, "min": 0.5, "max": 64.0, "step": 0.1}),
                "focus_m": ("FLOAT", {"default": 3.0, "min": 0.01, "max": 100000.0, "step": 0.1}),
                "sensor_width_mm": ("FLOAT", {"default": 36.0, "min": 1.0, "max": 100.0, "step": 0.1}),
                "quality": (["draft", "normal"], {"default": "normal"}),
                "max_radius_px": ("INT", {"default": 16, "min": 1, "max": 256, "step": 1}),
                "colorspace": (["srgb", "linear"], {"default": "srgb"}),
            },
            "optional": {
                "depth_mask": ("MASK",),
                "depth_image": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "coc_px")
    FUNCTION = "apply"
    CATEGORY = "Open Optics"

    def apply(self, image, focal_mm=50.0, f_number=2.8, focus_m=3.0, sensor_width_mm=36.0,
              quality="normal", max_radius_px=16, colorspace="srgb",
              depth_mask=None, depth_image=None):
        """Apply depth of field blur.

        focal_mm and sensor_width_mm are in millimetres, focus_m is in metres,
        f_number is unitless and max_radius_px is in pixels. Exactly one of
        depth_mask or depth_image (metres) must be connected. Returns a 2-tuple:
        a float32 IMAGE [B, H, W, C] in 0..1, and coc_px, a float32 MASK
        [B, H, W] with the blur radius divided by max_radius_px, clamped to 0..1.
        Raises ValueError for bad inputs.
        """
        common.check_image(image)
        if quality not in _LAYERS:
            raise ValueError(f"quality must be 'draft' or 'normal', got {quality!r}")
        depth = common.resolve_depth(image, depth_mask, depth_image)
        linear = common.to_linear(image, colorspace)
        radius = coc_radius_map(depth, focal_mm, f_number, focus_m, sensor_width_mm,
                                max_radius_px)
        result = composite_layers(linear, depth, radius, _LAYERS[quality])
        out = common.finish(common.from_linear(result, colorspace))
        coc = common.finish(radius / float(max_radius_px))
        return (out, coc)
