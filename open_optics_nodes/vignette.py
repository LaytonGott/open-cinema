"""Vignette node: apply cos^4 natural vignetting to an image."""

import torch

from open_optics import vignetting
from open_optics_nodes import common
from open_optics_nodes.device import get_device


class OpenOptics_Vignette:
    """Darken the image towards the corners with the cos^4 law."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "focal_mm": ("FLOAT", {"default": 35.0, "min": 0.1, "max": 2000.0, "step": 0.1}),
                "sensor_width_mm": ("FLOAT", {"default": 36.0, "min": 0.1, "max": 200.0, "step": 0.1}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "colorspace": (["srgb", "linear"], {"default": "srgb"}),
                "chunk_frames": common.CHUNK_FRAMES_INPUT,
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply"
    CATEGORY = "Open Optics"

    def apply(self, image, focal_mm=35.0, sensor_width_mm=36.0, strength=1.0, colorspace="srgb",
              chunk_frames=8):
        """Multiply the image by a vignette gain in linear light.

        focal_mm and sensor_width_mm are in millimetres; strength is unitless,
        0..1, with gain = 1 - strength * (1 - cos^4 gain). chunk_frames (a
        count of frames, >= 1, default 8) is how many frames are processed at
        a time on get_device(); the result does not depend on it. Returns a
        1-tuple with a CPU float32 IMAGE [B, H, W, C], 0-1. Raises ValueError
        if strength is outside 0..1 or the inputs are invalid.
        """
        common.check_chunk_frames(chunk_frames)
        common.check_image(image)
        focal_mm = common.require_positive("focal_mm", focal_mm)
        sensor_width_mm = common.require_positive("sensor_width_mm", sensor_width_mm)
        if not 0.0 <= strength <= 1.0:
            raise ValueError(f"strength must be between 0 and 1, got {strength}")
        h, w = image.shape[1], image.shape[2]
        device = get_device()
        rows = []
        for y in range(h):
            row = []
            for x in range(w):
                natural = vignetting.natural_vignette_px(focal_mm, x, y, sensor_width_mm, w, h)
                row.append(1.0 - strength * (1.0 - natural))
            rows.append(row)
        gain = torch.tensor(rows, dtype=torch.float32, device=device).reshape(1, h, w, 1)
        outs = []
        for start, stop in common.chunk_ranges(image.shape[0], chunk_frames):
            linear = common.to_linear(image[start:stop].to(device), colorspace)
            out = common.finish(common.from_linear(linear * gain, colorspace))
            outs.append(out.cpu().to(torch.float32))
        return (torch.cat(outs),)
