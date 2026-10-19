"""Anamorphic squeeze node: desqueeze or squeeze an image by resizing."""

import math
import time

import torch
import torch.nn.functional as F

from open_optics import anamorphic
from open_optics_nodes import common
from open_optics_nodes.device import get_device


class OpenOptics_Anamorphic:
    """Desqueeze or squeeze an image with an anamorphic squeeze factor."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "squeeze": ("FLOAT", {"default": 1.33, "min": 1.0, "max": 4.0, "step": 0.01}),
                "mode": (["desqueeze", "squeeze"], {"default": "desqueeze"}),
                "keep_width": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "chunk_frames": common.CHUNK_FRAMES_INPUT,
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply"
    CATEGORY = "Open Optics"

    def apply(self, image, squeeze=1.33, mode="desqueeze", keep_width=False, chunk_frames=8):
        """Resize the image by the squeeze factor with bilinear interpolation.

        squeeze is unitless, at least 1. Sizes are in pixels and come from the
        library: desqueeze widens (width * squeeze), or with keep_width
        shortens (height / squeeze); squeeze mode is the inverse. chunk_frames
        (a count of frames, >= 1, default 8) is how many frames are processed
        at a time on get_device(); the result does not depend on it. Returns
        a 1-tuple with a CPU float32 IMAGE [B, H, W, C], 0-1. Raises
        ValueError if squeeze is below 1, mode is unknown or chunk_frames is
        invalid.
        """
        common.check_chunk_frames(chunk_frames)
        common.check_image(image)
        if not math.isfinite(squeeze):
            raise ValueError(f"squeeze must be finite, got {squeeze}")
        if squeeze < 1.0:
            raise ValueError(f"squeeze must be at least 1.0, got {squeeze}")
        common.require_choice("mode", mode, ("desqueeze", "squeeze"))
        h, w = image.shape[1], image.shape[2]
        lib_mode = "shorten" if keep_width else "widen"
        size_fn = anamorphic.desqueeze_size if mode == "desqueeze" else anamorphic.squeeze_size
        new_w, new_h = size_fn(w, h, squeeze, lib_mode)
        new_w, new_h = max(1, round(new_w)), max(1, round(new_h))
        t0 = time.perf_counter()
        device = get_device()
        worked_on = device
        outs = []
        for start, stop in common.chunk_ranges(image.shape[0], chunk_frames):
            x = image[start:stop].to(device).permute(0, 3, 1, 2)
            x = F.interpolate(x, size=(new_h, new_w), mode="bilinear", align_corners=False)
            out = common.finish(x.permute(0, 2, 3, 1))
            worked_on = out
            outs.append(out.cpu().to(torch.float32))
        if outs:
            result = torch.cat(outs)
        else:
            result = torch.zeros((0, new_h, new_w, image.shape[3]), dtype=torch.float32)
        common.log_call("OpenOptics_Anamorphic", worked_on, image.shape[0], chunk_frames,
                        time.perf_counter() - t0)
        return (result,)
