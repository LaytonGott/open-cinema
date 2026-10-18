"""Focal Crop node: simulate a longer focal length by a centre crop."""

import math

import torch.nn.functional as F

from open_optics import fov
from open_optics_nodes import common

_REFERENCE_DIMENSION_MM = 36.0  # any width works; the ratio cancels it


class OpenOptics_FocalCrop:
    """Centre-crop an image so a source focal length looks like a longer target focal length."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "source_focal_mm": ("FLOAT", {"default": 24.0, "min": 0.1, "max": 2000.0, "step": 0.1}),
                "target_focal_mm": ("FLOAT", {"default": 50.0, "min": 0.1, "max": 2000.0, "step": 0.1}),
                "output_size": (["original", "cropped"], {"default": "original"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "crop"
    CATEGORY = "Open Optics"

    def crop(self, image, source_focal_mm=24.0, target_focal_mm=50.0, output_size="original"):
        """Crop the image centre to the target focal length's view (focals in mm).

        Each side keeps the fraction tan(half angle of target) / tan(half angle
        of source) = source / target. output_size 'original' resizes back to
        the input size (bilinear); 'cropped' keeps the crop size. Returns a
        1-tuple with an IMAGE [B, H', W', C], 0-1. Raises ValueError if either
        focal is <= 0 or target < source.
        """
        common.check_image(image)
        if source_focal_mm <= 0 or target_focal_mm <= 0:
            raise ValueError("focal lengths must be positive")
        if target_focal_mm < source_focal_mm:
            raise ValueError("target_focal_mm must be >= source_focal_mm")
        if output_size not in ("original", "cropped"):
            raise ValueError(f"output_size must be 'original' or 'cropped', got {output_size!r}")
        half_src = math.radians(fov.angle_of_view(source_focal_mm, _REFERENCE_DIMENSION_MM)) / 2
        half_tgt = math.radians(fov.angle_of_view(target_focal_mm, _REFERENCE_DIMENSION_MM)) / 2
        ratio = math.tan(half_tgt) / math.tan(half_src)  # equals source / target
        h, w = image.shape[1], image.shape[2]
        ch = min(h, max(1, round(h * ratio)))
        cw = min(w, max(1, round(w * ratio)))
        top, left = (h - ch) // 2, (w - cw) // 2
        out = image[:, top:top + ch, left:left + cw, :]
        if output_size == "original" and (ch, cw) != (h, w):
            nchw = out.permute(0, 3, 1, 2)
            nchw = F.interpolate(nchw, size=(h, w), mode="bilinear", align_corners=False)
            out = nchw.permute(0, 2, 3, 1)
        return (common.finish(out),)
