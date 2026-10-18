"""Chromatic fringing: pixels and unitless scale settings.

The red and blue channels are scaled radially about the principal point
relative to green, which stays fixed. Settings are unitless; shifts are in
pixels.
"""

from open_optics.pixels import _principal_point
from open_optics.validation import require_finite


def channel_scales(red=0.0, blue=0.0):
    """Scale factors of the red and blue channels relative to green.

    red and blue are unitless settings (0.0 means no fringe). Returns the
    tuple (1 + red, 1 + blue), unitless; green is always 1.0.
    """
    r = require_finite("red", red)
    b = require_finite("blue", blue)
    return 1.0 + r, 1.0 + b


def fringe_shift_px(
    px, py, width_px, height_px, red=0.0, blue=0.0, cx=None, cy=None
):
    """Shift of the red and blue channels at a pixel position, in pixels.

    px, py, cx, cy, width_px and height_px are in pixels; red and blue are
    unitless settings. cx and cy default to (width_px - 1) / 2 and
    (height_px - 1) / 2. Returns ((red_dx, red_dy), (blue_dx, blue_dy)) in
    pixels, where each shift is (px - cx, py - cy) * setting, so it is
    exactly (0.0, 0.0) at the centre.
    """
    x = require_finite("px", px)
    y = require_finite("py", py)
    r = require_finite("red", red)
    b = require_finite("blue", blue)
    cx, cy = _principal_point(width_px, height_px, cx, cy)
    dx = x - cx
    dy = y - cy
    return (dx * r, dy * r), (dx * b, dy * b)
