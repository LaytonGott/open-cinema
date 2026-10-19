"""Relative depth to metric depth mapping.

Input depth values are unitless relative depth (e.g. a depth-model output).
Metric distances (near_m, far_m and results) are in metres. Percentiles are
in the range 0 to 100.
"""

import math


def validate_depth_params(near_m, far_m, low_percentile, high_percentile):
    """Check depth mapping parameters.

    near_m and far_m are distances in metres; low_percentile and
    high_percentile are percentiles from 0 to 100. Returns None. Raises
    ValueError unless 0 < near_m < far_m and 0 <= low_percentile <
    high_percentile <= 100.
    """
    if not near_m > 0:
        raise ValueError(f"near_m must be greater than 0, got {near_m}")
    if not far_m > near_m:
        raise ValueError(
            f"far_m must be greater than near_m, got far_m={far_m}, near_m={near_m}"
        )
    if not 0 <= low_percentile < high_percentile <= 100:
        raise ValueError(
            "percentiles must satisfy 0 <= low < high <= 100, got "
            f"low={low_percentile}, high={high_percentile}"
        )


def percentile(values, q):
    """Percentile of unitless values, with linear interpolation.

    q is in percent (0 to 100); the position is q/100*(n-1) in the sorted
    values, as in torch.quantile. Returns a float in the same unit as values.
    Raises ValueError for empty values or q outside 0..100.
    """
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("values must not be empty")
    if not 0 <= q <= 100:
        raise ValueError(f"q must be between 0 and 100, got {q}")
    pos = q / 100 * (n - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return float(ordered[lo] + (ordered[hi] - ordered[lo]) * frac)


def fit_depth_mapping(d_lo, d_hi, near_m, far_m, inverse_depth=True):
    """Fit the linear parameters (a, b) mapping relative depth to metres.

    d_lo and d_hi are unitless relative depths that map to near_m and far_m
    (metres). With inverse_depth, Z = 1/(a*d+b) with a=(1/near-1/far)/(d_hi-d_lo)
    and b=1/near-a*d_hi (so d_hi maps to near_m); otherwise Z = a*d+b with
    a=(far-near)/(d_hi-d_lo) and b=near-a*d_lo. Returns the tuple (a, b);
    if d_hi == d_lo returns (0.0, (near_m+far_m)/2), a constant in metres.
    """
    if d_hi == d_lo:
        return (0.0, (near_m + far_m) / 2)
    if inverse_depth:
        a = (1 / near_m - 1 / far_m) / (d_hi - d_lo)
        b = 1 / near_m - a * d_hi
    else:
        a = (far_m - near_m) / (d_hi - d_lo)
        b = near_m - a * d_lo
    return (a, b)


def metric_depth_coefficients(d_lo, d_hi, near_m, far_m, inverse_depth):
    """Coefficients that map a relative depth d to metres.

    d_lo and d_hi are unitless relative depths that map to the limits near_m
    and far_m as in fit_depth_mapping; near_m and far_m are in metres. Returns the
    tuple (a, b, reciprocal) of floats: the distance in metres is
    Z = 1/(a*d+b) when reciprocal is True, else Z = a*d+b. If d_hi == d_lo
    returns (0.0, (near_m+far_m)/2, False), a constant in metres.
    """
    if d_hi == d_lo:
        return (0.0, (near_m + far_m) / 2, False)
    a, b = fit_depth_mapping(d_lo, d_hi, near_m, far_m, inverse_depth)
    return (a, b, bool(inverse_depth))


def depth_to_metric(d, d_lo, d_hi, near_m, far_m, inverse_depth=True):
    """Convert a unitless relative depth d to metres.

    See fit_depth_mapping for d_lo, d_hi, near_m, far_m (metres) and the
    inverse_depth model. Returns the distance in metres clamped to
    [near_m, far_m]; if d_hi == d_lo returns (near_m+far_m)/2.
    """
    if d_hi == d_lo:
        return (near_m + far_m) / 2
    a, b = fit_depth_mapping(d_lo, d_hi, near_m, far_m, inverse_depth)
    if inverse_depth:
        denom = a * d + b
        z = far_m if denom <= 0 else 1 / denom
    else:
        z = a * d + b
    return min(max(z, near_m), far_m)


def subject_pixel(x, y, width, height):
    """Convert a subject position to a pixel index.

    x and y are fractions (0 to 1) of the image width and height; width and
    height are in pixels. Returns the tuple (col, row) of ints,
    (round(x*(width-1)), round(y*(height-1))).
    """
    return (round(x * (width - 1)), round(y * (height - 1)))


def subject_median(values):
    """Median of the unitless depth values in the subject region.

    values is an iterable of unitless relative depths. Returns the median as
    a float in the same unit as values (the mean of the two middle values for
    an even count, as torch.quantile(0.5)). Raises ValueError for empty
    values or any non-finite value.
    """
    items = list(values)
    if not items:
        raise ValueError("values must not be empty")
    if not all(math.isfinite(v) for v in items):
        raise ValueError("values must all be finite")
    return percentile(items, 50)
