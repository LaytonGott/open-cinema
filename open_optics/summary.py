"""Text summaries of lens setups. Units: lengths in millimetres (mm) or metres (m), angles in degrees (deg)."""

import math

from open_optics.fov import field_of_view
from open_optics.validation import require_positive


def _fmt(value):
    """Format a number for display.

    value is a unitless float (the caller's unit applies). Returns 'inf' for
    math.inf, otherwise the value as a string with 2 decimals, e.g. '39.60'.
    """
    if value == math.inf:
        return "inf"
    return f"{value:.2f}"


def shot_summary(sensor, lens, f_number, focus_m):
    """Summarise the optics of a shot as text.

    sensor is an open_optics.sensor.Sensor (millimetres), lens an
    open_optics.lens.Lens (focal length in millimetres), f_number is unitless
    and focus_m is the focus distance in metres. Returns a str of lines:
    focal length (mm), f-number, focus (m), horizontal, vertical and diagonal
    FOV (deg), crop factor and full-frame equivalent focal length (mm).
    Raises ValueError if focus_m or f_number is not positive and finite.
    """
    focus = require_positive("focus_m", focus_m)
    f_stop = require_positive("f_number", f_number)
    fov = field_of_view(lens.focal_mm, sensor.width_mm, sensor.height_mm, lens.squeeze)
    lines = [
        f"Focal length: {_fmt(lens.focal_mm)} mm",
        f"F-number: {_fmt(f_stop)}",
        f"Focus: {_fmt(focus)} m",
        f"Horizontal FOV: {_fmt(fov.hfov_deg)} deg",
        f"Vertical FOV: {_fmt(fov.vfov_deg)} deg",
        f"Diagonal FOV: {_fmt(fov.dfov_deg)} deg",
        f"Crop factor: {_fmt(fov.crop_factor)}",
        f"Equivalent focal length: {_fmt(fov.equiv_focal_ff_mm)} mm",
    ]
    return "\n".join(lines)
