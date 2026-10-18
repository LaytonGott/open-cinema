"""Focus breathing. Lengths are in millimetres in; results are unitless."""

import math

from open_optics.validation import (
    require_finite,
    require_positive,
    require_positive_or_inf,
)


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


def breathing_scale(focal_mm, focus_mm, reference_focus_mm, strength=1.0):
    """Return the unitless image scale change at focus_mm versus reference_focus_mm.

    focal_mm, focus_mm and reference_focus_mm are in millimetres
    (math.inf allowed for the two focus distances). strength is unitless and
    must be in 0-1, otherwise ValueError is raised. Computed as
    (focus_magnification(focal_mm, focus_mm) /
    focus_magnification(focal_mm, reference_focus_mm)) ** strength. Returns a
    unitless float, 1.0 at the reference focus or with strength 0.
    """
    s = require_finite("strength", strength)
    if not 0.0 <= s <= 1.0:
        raise ValueError(f"strength must be in 0-1, got {strength}")
    ratio = focus_magnification(focal_mm, focus_mm) / focus_magnification(
        focal_mm, reference_focus_mm
    )
    return ratio**s
