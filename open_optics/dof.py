"""Thin-lens depth of field. All lengths are in millimetres."""

import math

from open_optics.validation import require_positive


def hyperfocal_mm(focal_mm, f_number, coc_mm):
    """Return the hyperfocal distance in millimetres.

    focal_mm is the focal length in millimetres, f_number is the unitless
    aperture (N) and coc_mm is the circle of confusion in millimetres.
    Computed as f^2 / (N * c) + f.
    """
    f = require_positive("focal_mm", focal_mm)
    n = require_positive("f_number", f_number)
    c = require_positive("coc_mm", coc_mm)
    return f * f / (n * c) + f


def hyperfocal_focus_mm(focal_mm, f_number, coc_mm):
    """Return the focus distance in millimetres that puts the far DoF limit at infinity.

    focal_mm is the focal length in millimetres, f_number is the unitless
    aperture (N) and coc_mm is the circle of confusion in millimetres.
    This equals the hyperfocal distance.
    """
    return hyperfocal_mm(focal_mm, f_number, coc_mm)


def dof_limits_mm(focal_mm, f_number, focus_mm, coc_mm):
    """Return the depth-of-field limits (near_mm, far_mm) in millimetres.

    focal_mm, focus_mm (subject distance) and coc_mm are in millimetres;
    f_number is unitless. far_mm is math.inf when the focus distance is at or
    beyond the hyperfocal distance. Raises ValueError if focus_mm is infinite.
    """
    f = require_positive("focal_mm", focal_mm)
    n = require_positive("f_number", f_number)
    s = require_positive("focus_mm", focus_mm)
    c = require_positive("coc_mm", coc_mm)
    if math.isinf(s):
        raise ValueError(f"focus_mm must be finite, got {focus_mm}")
    h = hyperfocal_mm(f, n, c)
    near = s * (h - f) / (h + s - 2 * f)
    far = s * (h - f) / (h - s) if s < h else math.inf
    return (near, far)


def dof_summary(focal_mm, f_number, focus_mm, coc_mm):
    """Return a dict summarising depth of field, with all values in millimetres.

    focal_mm, focus_mm and coc_mm are in millimetres; f_number is unitless.
    Keys: 'hyperfocal_mm', 'near_mm', 'far_mm' and 'total_mm', where total_mm
    is far_mm - near_mm, or math.inf when far_mm is infinity. Divide any value
    by 1000 to get metres.
    """
    near, far = dof_limits_mm(focal_mm, f_number, focus_mm, coc_mm)
    return {
        "hyperfocal_mm": hyperfocal_mm(focal_mm, f_number, coc_mm),
        "near_mm": near,
        "far_mm": far,
        "total_mm": math.inf if math.isinf(far) else far - near,
    }
