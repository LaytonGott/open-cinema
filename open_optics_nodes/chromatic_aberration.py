"""Chromatic Aberration node: radial scale fringing of red and blue."""

import time

import torch
import torch.nn.functional as F

from open_optics import chromatic
from open_optics_nodes import common
from open_optics_nodes.device import get_device


def _scaled_channel(channel, scale):
    """Resample a [B, H, W] channel so content at radius r moves to r * scale."""
    b, h, w = channel.shape
    dev = channel.device
    ys = torch.linspace(-1.0, 1.0, h, device=dev) if h > 1 else torch.zeros(1, device=dev)
    xs = torch.linspace(-1.0, 1.0, w, device=dev) if w > 1 else torch.zeros(1, device=dev)
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
                "ca_r": ("FLOAT", {"default": 0.0, "min": -0.1, "max": 0.1, "step": 0.0001}),
                "ca_b": ("FLOAT", {"default": 0.0, "min": -0.1, "max": 0.1, "step": 0.0001}),
            },
            "optional": {
                "chunk_frames": common.CHUNK_FRAMES_INPUT,
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply"
    CATEGORY = "Open Optics"

    def apply(self, image, ca_r=0.0, ca_b=0.0, chunk_frames=8):
        """Scale red and blue radially about the image centre; green is fixed.

        ca_r and ca_b are unitless radial scale offsets (scale = 1 + offset);
        content at radius r (pixels) in the source appears at r * scale.
        Both default to 0, which is the identity (output equals input).
        chunk_frames (a count of frames, >= 1, default 8) is how many frames
        are processed at a time on get_device(); the result does not depend
        on it. Returns a 1-tuple with a CPU float32 IMAGE [B, H, W, C], 0-1.
        Channels beyond the third are untouched.
        """
        common.check_chunk_frames(chunk_frames)
        common.check_image(image)
        sr, sb = chromatic.channel_scales(ca_r, ca_b)
        t0 = time.perf_counter()
        device = get_device()
        worked_on = device
        outs = []
        for start, stop in common.chunk_ranges(image.shape[0], chunk_frames):
            piece = image[start:stop].to(device)
            out = piece.clone()
            if piece.shape[3] >= 3:
                if sr != 1.0:
                    out[..., 0] = _scaled_channel(piece[..., 0], sr)
                if sb != 1.0:
                    out[..., 2] = _scaled_channel(piece[..., 2], sb)
            done = common.finish(out)
            worked_on = done
            outs.append(done.cpu().to(torch.float32))
        if outs:
            result = torch.cat(outs)
        else:
            result = torch.zeros(tuple(image.shape), dtype=torch.float32)
        common.log_call("OpenOptics_ChromaticAberration", worked_on, image.shape[0],
                        chunk_frames, time.perf_counter() - t0)
        return (result,)
