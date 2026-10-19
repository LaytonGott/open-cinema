"""Depth of Field node for the Open Optics pack (CPU torch tensors)."""

import math

import torch

from open_optics_nodes import common
from open_optics_nodes.device import get_device
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
                "max_radius_px": ("INT", {"default": 16, "min": 0, "max": 256, "step": 1}),
                "colorspace": (["srgb", "linear"], {"default": "srgb"}),
                "chunk_frames": common.CHUNK_FRAMES_INPUT,
            },
            "optional": {
                "depth_mask": ("MASK",),
                "depth_image": ("IMAGE",),
                "max_layers": ("INT", {"default": 12, "min": 1, "max": 64, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "coc_px")
    FUNCTION = "apply"
    CATEGORY = "Open Optics"

    def apply(self, image, focal_mm=50.0, f_number=2.8, focus_m=3.0, sensor_width_mm=36.0,
              quality="normal", max_radius_px=16, colorspace="srgb",
              depth_mask=None, depth_image=None, chunk_frames=8, max_layers=12):
        """Apply depth of field blur.

        focal_mm and sensor_width_mm are in millimetres, focus_m is in metres,
        f_number is unitless and max_radius_px is in pixels. Exactly one of
        depth_mask or depth_image (metres) must be connected. Returns a 2-tuple:
        a float32 IMAGE [B, H, W, C] in 0..1, and coc_px, a float32 MASK
        [B, H, W] with the blur radius divided by max_radius_px, clamped to 0..1.
        A max_radius_px of 0 skips blurring: the image is returned unchanged
        with an all-zero coc_px. Raises ValueError for bad inputs, including a
        negative or non-finite max_radius_px. chunk_frames (a count of frames,
        >= 1, default 8) is how many frames are processed at a time; both
        outputs are built chunk by chunk and do not depend on it. max_layers
        (a count of layers, an integer from 1 to 64, default 12) caps the
        number of blurred depth layers per frame.
        """
        common.check_chunk_frames(chunk_frames)
        if (isinstance(max_layers, bool) or not isinstance(max_layers, int)
                or not 1 <= max_layers <= 64):
            raise ValueError(f"max_layers must be an integer from 1 to 64, got {max_layers!r}")
        common.check_image(image)
        common.require_positive("focal_mm", focal_mm)
        common.require_positive("f_number", f_number)
        common.require_positive("focus_m", focus_m)
        common.require_positive("sensor_width_mm", sensor_width_mm)
        if not math.isfinite(max_radius_px) or max_radius_px < 0:
            raise ValueError(f"max_radius_px must be finite and >= 0, got {max_radius_px}")
        common.require_choice("quality", quality, list(_LAYERS))
        depth = common.resolve_depth(image, depth_mask, depth_image)
        if max_radius_px == 0:
            return (common.finish(image.clone()),
                    torch.zeros(image.shape[:3], dtype=torch.float32))
        device = get_device()
        outs, cocs = [], []
        for start, stop in common.chunk_ranges(image.shape[0], chunk_frames):
            linear = common.to_linear(image[start:stop].to(device), colorspace)
            depth_c = depth[start:stop].to(device)
            radius = coc_radius_map(depth_c, focal_mm, f_number, focus_m, sensor_width_mm,
                                    max_radius_px)
            result = composite_layers(linear, depth_c, radius, _LAYERS[quality], focus_m,
                                       max_layers)
            outs.append(common.finish(common.from_linear(result, colorspace)).cpu().to(torch.float32))
            cocs.append(common.finish(radius / float(max_radius_px)).cpu().to(torch.float32))
        return (torch.cat(outs), torch.cat(cocs))
