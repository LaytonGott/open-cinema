"""Depth helpers for the Open Optics nodes (CPU torch tensors)."""

import math

import torch

from open_optics.depth import metric_depth_coefficients, validate_depth_params
from open_optics_nodes import common
from open_optics_nodes.device import get_device


def depth_percentile_range(depth, low_percentile, high_percentile):
    """Return (d_lo, d_hi) percentile values of a whole depth batch.

    The whole tensor (all frames together) is flattened, non-finite values
    (NaN, +-inf) are dropped, and the rest is sorted. Percentiles are 0 to 100
    and depth values are unitless. Uses linear interpolation at position
    q/100*(n-1) over the n finite values, the same as torch.quantile. Returns
    two Python floats. Raises ValueError for an empty tensor, a tensor with no
    finite values, or a percentile outside 0 to 100.
    """
    flat = depth.detach().reshape(-1).to(torch.float64)
    if flat.numel() == 0:
        raise ValueError("depth must not be empty")
    flat = flat[torch.isfinite(flat)]
    n = flat.numel()
    if n == 0:
        raise ValueError("depth has no finite values")
    sorted_vals, _ = torch.sort(flat)

    def at(q):
        if not 0.0 <= q <= 100.0:
            raise ValueError(f"percentile must be 0 to 100, got {q}")
        pos = q / 100.0 * (n - 1)
        lo = math.floor(pos)
        hi = math.ceil(pos)
        frac = pos - lo
        a = float(sorted_vals[lo])
        b = float(sorted_vals[hi])
        return a + (b - a) * frac

    return at(low_percentile), at(high_percentile)


def depth_to_metric_tensor(depth, near_m, far_m, inverse_depth, low_percentile, high_percentile):
    """Convert a relative depth tensor of any shape to metres.

    near_m and far_m are distances in metres; percentiles are 0 to 100 and pick
    the depth values that map to the limits (see depth_percentile_range).
    Returns a float32 tensor of the same shape in metres, within [near_m, far_m].
    Non-finite depth entries are ignored in the fit and replaced before the
    mapping: NaN and -inf become d_lo, +inf becomes d_hi, so the result is
    always finite. Raises ValueError for bad near/far/percentiles or a depth
    with no finite values.
    """
    validate_depth_params(near_m, far_m, low_percentile, high_percentile)
    d_lo, d_hi = depth_percentile_range(depth, low_percentile, high_percentile)
    return _map_to_metric(depth, d_lo, d_hi, near_m, far_m, inverse_depth)


def _map_to_metric(depth, d_lo, d_hi, near_m, far_m, inverse_depth):
    """Map a depth tensor to metres with an already fitted (d_lo, d_hi).

    near_m and far_m are in metres; d_lo and d_hi are unitless depth values.
    Returns a float32 tensor of the same shape and device in metres.
    """
    a, b, reciprocal = metric_depth_coefficients(d_lo, d_hi, near_m, far_m, inverse_depth)
    d = depth.detach().to(torch.float64)
    d = torch.where(torch.isposinf(d), torch.full_like(d, d_hi), d)
    d = torch.where(torch.isfinite(d), d, torch.full_like(d, d_lo))
    v = a * d + b
    if reciprocal:
        z = 1.0 / torch.clamp(v, 1.0 / far_m, 1.0 / near_m)
    else:
        z = torch.clamp(v, near_m, far_m)
    return z.to(torch.float32)


class OpenOptics_DepthToMetric:
    """Convert a relative depth map to metric depth in metres."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "near_m": ("FLOAT", {"default": 0.5, "min": 0.001, "max": 100000.0, "step": 0.1}),
                "far_m": ("FLOAT", {"default": 10.0, "min": 0.001, "max": 100000.0, "step": 0.1}),
                "inverse_depth": ("BOOLEAN", {"default": True}),
                "low_percentile": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "high_percentile": ("FLOAT", {"default": 98.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "chunk_frames": common.CHUNK_FRAMES_INPUT,
            },
            "optional": {
                "depth_mask": ("MASK",),
                "depth_image": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("MASK", "IMAGE")
    RETURN_NAMES = ("depth_m", "preview")
    FUNCTION = "convert"
    CATEGORY = "Open Optics"

    def convert(self, near_m=0.5, far_m=10.0, inverse_depth=True, low_percentile=2.0,
                high_percentile=98.0, depth_mask=None, depth_image=None, chunk_frames=8):
        """Convert relative depth to metres.

        near_m and far_m are in metres; percentiles are 0 to 100. Exactly one
        of depth_mask or depth_image must be connected. The percentile fit uses
        the whole batch once; chunk_frames (a count of frames, >= 1, default 8)
        is how many frames are then converted at a time on get_device(), and
        the result does not depend on it. Returns a 2-tuple of CPU tensors:
        depth_m, a float32 MASK [B, H, W] in metres, and preview, a float32
        IMAGE [B, H, W, 3] with (far_m - Z) / (far_m - near_m) clamped to 0..1.
        Raises ValueError for bad inputs.
        """
        common.check_chunk_frames(chunk_frames)
        depth = common.resolve_depth(None, depth_mask, depth_image)
        validate_depth_params(near_m, far_m, low_percentile, high_percentile)
        d_lo, d_hi = depth_percentile_range(depth, low_percentile, high_percentile)
        device = get_device()
        zs = []
        previews = []
        for start, stop in common.chunk_ranges(depth.shape[0], chunk_frames):
            z = _map_to_metric(depth[start:stop].to(device), d_lo, d_hi,
                               near_m, far_m, inverse_depth)
            shade = torch.clamp((far_m - z) / (far_m - near_m), 0.0, 1.0)
            preview = shade.unsqueeze(-1).repeat(1, 1, 1, 3)
            zs.append(z.cpu().to(torch.float32))
            previews.append(preview.cpu().to(torch.float32))
        return (torch.cat(zs), torch.cat(previews))
