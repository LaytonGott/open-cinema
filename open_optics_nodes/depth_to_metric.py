"""Depth helpers for the Open Optics nodes (CPU torch tensors)."""

import math

import torch

from open_optics.depth import metric_depth_coefficients, validate_depth_params


def depth_percentile_range(depth, low_percentile, high_percentile):
    """Return (d_lo, d_hi) percentile values of a whole depth batch.

    The whole tensor (all frames together) is flattened and sorted. Percentiles
    are 0 to 100 and depth values are unitless. Uses linear interpolation at
    position q/100*(n-1), the same as torch.quantile. Returns two Python floats.
    Raises ValueError for an empty tensor or a percentile outside 0 to 100.
    """
    flat = depth.detach().reshape(-1).to(torch.float64)
    n = flat.numel()
    if n == 0:
        raise ValueError("depth must not be empty")
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
    Raises ValueError for bad near/far/percentiles.
    """
    validate_depth_params(near_m, far_m, low_percentile, high_percentile)
    d_lo, d_hi = depth_percentile_range(depth, low_percentile, high_percentile)
    a, b, reciprocal = metric_depth_coefficients(d_lo, d_hi, near_m, far_m, inverse_depth)
    v = a * depth.detach().to(torch.float64) + b
    if reciprocal:
        z = 1.0 / torch.clamp(v, 1.0 / far_m, 1.0 / near_m)
    else:
        z = torch.clamp(v, near_m, far_m)
    return z.to(torch.float32)
