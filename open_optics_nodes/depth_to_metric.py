"""Depth helpers for the Open Optics nodes (CPU torch tensors)."""

import math

import torch


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
