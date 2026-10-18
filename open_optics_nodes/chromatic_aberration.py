"""Chromatic Aberration node: radial scale fringing of red and blue."""

import torch
import torch.nn.functional as F

from open_optics import chromatic
from open_optics_nodes import common


def _scaled_channel(channel, scale):
    """Resample a [B, H, W] channel so content at radius r moves to r * scale."""
    b, h, w = channel.shape
    ys = torch.linspace(-1.0, 1.0, h) if h > 1 else torch.zeros(1)
    xs = torch.linspace(-1.0, 1.0, w) if w > 1 else torch.zeros(1)
    gy, gx = torch.meshgrid(ys, xs, indexing="ij")
    grid = torch.stack((gx, gy), dim=-1) / scale
    grid = grid.unsqueeze(0).expand(b, h, w, 2)
    out = F.grid_sample(
        channel.unsqueeze(1), grid, mode="bilinear", padding_mode="border", align_corners=True
    )
    return out[:, 0]


class OpenOptics_ChromaticAberration:
    """Scale the red and blue channels radially relative to green."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "ca_r": ("FLOAT", {"default": 0.0005, "min": -0.1, "max": 0.1, "step": 0.0001}),
                "ca_b": ("FLOAT", {"default": -0.0005, "min": -0.1, "max": 0.1, "step": 0.0001}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply"
    CATEGORY = "Open Optics"

    def apply(self, image, ca_r=0.0005, ca_b=-0.0005):
        """Scale red and blue radially about the image centre; green is fixed.

        ca_r and ca_b are unitless radial scale offsets (scale = 1 + offset);
        content at radius r (pixels) in the source appears at r * scale.
        Returns a 1-tuple with an IMAGE [B, H, W, C], 0-1. Channels beyond the
        third are untouched.
        """
        common.check_image(image)
        sr, sb = chromatic.channel_scales(ca_r, ca_b)
        out = image.clone()
        if image.shape[3] >= 3:
            if sr != 1.0:
                out[..., 0] = _scaled_channel(image[..., 0], sr)
            if sb != 1.0:
                out[..., 2] = _scaled_channel(image[..., 2], sb)
        return (common.finish(out),)
