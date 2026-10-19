"""Focal Crop node: simulate a longer focal length by a centre crop."""

import math
import time

import torch
import torch.nn.functional as F

from open_optics import fov
from open_optics_nodes import common
from open_optics_nodes.device import get_device

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
                "chunk_frames": common.CHUNK_FRAMES_INPUT,
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "crop"
    CATEGORY = "Open Optics"

    def crop(self, image, source_focal_mm=24.0, target_focal_mm=50.0, output_size="original",
             chunk_frames=8):
        """Crop the image centre to the target focal length's view (focals in mm).

        Each side keeps the fraction tan(half angle of target) / tan(half angle
        of source) = source / target. output_size 'original' resizes back to
        the input size (bilinear); 'cropped' keeps the crop size. Returns a
        1-tuple with an IMAGE [B, H', W', C], 0-1. Raises ValueError if either
        focal is <= 0 or target < source. chunk_frames (a count of frames, >= 1,
        default 8) is how many frames are processed at a time on get_device();
        the result does not depend on it and is returned on the CPU as float32.
        """
        t0 = time.perf_counter()
        common.check_chunk_frames(chunk_frames)
        common.check_image(image)
        source_focal_mm = common.require_positive("source_focal_mm", source_focal_mm)
        target_focal_mm = common.require_positive("target_focal_mm", target_focal_mm)
        if target_focal_mm < source_focal_mm:
            raise ValueError(
                f"target_focal_mm must be at least source_focal_mm ({source_focal_mm}), "
                f"got {target_focal_mm}"
            )
        common.require_choice("output_size", output_size, ("original", "cropped"))
        half_src = math.radians(fov.angle_of_view(source_focal_mm, _REFERENCE_DIMENSION_MM)) / 2
        half_tgt = math.radians(fov.angle_of_view(target_focal_mm, _REFERENCE_DIMENSION_MM)) / 2
        ratio = math.tan(half_tgt) / math.tan(half_src)  # equals source / target
        h, w = image.shape[1], image.shape[2]
        ch = min(h, max(1, round(h * ratio)))
        cw = min(w, max(1, round(w * ratio)))
        top, left = (h - ch) // 2, (w - cw) // 2
        device = get_device()
        outs = []
        worked_on = device
        for start, stop in common.chunk_ranges(image.shape[0], chunk_frames):
            out = image[start:stop, top:top + ch, left:left + cw, :].to(device)
            if output_size == "original" and (ch, cw) != (h, w):
                nchw = out.permute(0, 3, 1, 2)
                nchw = F.interpolate(nchw, size=(h, w), mode="bilinear", align_corners=False)
                out = nchw.permute(0, 2, 3, 1)
            out = common.finish(out)
            worked_on = out
            outs.append(out.cpu().to(torch.float32))
        result = torch.cat(outs)
        common.log_call("OpenOptics_FocalCrop", worked_on, image.shape[0], chunk_frames,
                        time.perf_counter() - t0)
        return (result,)
