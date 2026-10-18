"""Focus breathing. Lengths are in millimetres in; results are unitless."""

import math

from open_optics.validation import require_positive, require_positive_or_inf


def focus_magnification(focal_mm, focus_mm):
    """Return the unitless image magnification relative to infinity focus.

    focal_mm is the focal length in millimetres and focus_mm is the focus
    distance in millimetres (math.inf for infinity focus). Computed as
    focus_mm / (focus_mm - focal_mm) and returns 1.0 at infinity. Raises
    ValueError if focus_mm <= focal_mm.
    """
    f = require_positive("focal_mm", focal_mm)
    d = require_positive_or_inf("focus_mm", focus_mm)
    if math.isinf(d):
        return 1.0
    if d <= f:
        raise ValueError(f"focus_mm must be greater than focal_mm, got {focus_mm}")
    return d / (d - f)
