"""Thin-lens depth of field. All lengths are in millimetres."""

import math

from open_optics.validation import require_positive, require_positive_or_inf


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


def focus_for_range_mm(focal_mm, f_number, coc_mm, near_mm, far_mm):
    """Return the focus distance in millimetres that keeps near_mm to far_mm sharp.

    focal_mm, coc_mm, near_mm and far_mm are in millimetres (far_mm may be
    math.inf); f_number is unitless. Returns the farthest focus distance that
    still covers the range, which is the hyperfocal distance when far_mm is
    infinite. Raises ValueError if near_mm > far_mm or if the range cannot be
    covered at this aperture.
    """
    near = require_positive("near_mm", near_mm)
    far = require_positive_or_inf("far_mm", far_mm)
    if near > far:
        raise ValueError(f"near_mm must not exceed far_mm, got {near_mm} > {far_mm}")
    big_h = hyperfocal_mm(focal_mm, f_number, coc_mm)
    f = focal_mm
    h = big_h - f
    s2 = big_h if math.isinf(far) else far * (h + f) / (h + far)
    s1 = near * (h - f) / (h - near) if near < h else math.inf
    if s2 > s1:
        raise ValueError(
            "range near-far cannot be covered at this aperture; stop down or narrow the range"
        )
    return s2


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
