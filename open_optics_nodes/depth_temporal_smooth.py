"""Temporal depth smoothing node for Open Optics (CPU torch tensors)."""

import torch

from open_optics.temporal import smooth_depth_sequence


class OpenOptics_DepthTemporalSmooth:
    """Smooth a metric depth sequence over time."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "depth": ("MASK",),
                "strength": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("depth_m",)
    FUNCTION = "smooth"
    CATEGORY = "Open Optics"

    def smooth(self, depth, strength=0.7):
        """Smooth a depth sequence over time.

        depth is a MASK [B, H, W] of depth in metres (one frame per batch
        entry); strength is unitless, 0 to 1. Returns a 1-tuple holding a
        float32 CPU MASK [B, H, W] of smoothed depth in metres. Raises
        ValueError if depth is not a 3-dimensional tensor.
        """
        if not isinstance(depth, torch.Tensor) or depth.dim() != 3:
            raise ValueError("depth must be a 3-dimensional tensor [B, H, W]")
        frames = depth.detach().cpu().to(torch.float64).tolist()
        out = smooth_depth_sequence(frames, strength)
        return (torch.tensor(out, dtype=torch.float32).reshape(depth.shape),)
