"""Natural vignetting: millimetres in, brightness fractions 0-1 out."""

import math

from open_optics.pixels import _principal_point
from open_optics.validation import require_finite, require_positive


def natural_vignette(focal_mm, x_mm, y_mm=0.0):
    """Cos^4 natural vignetting brightness at a sensor position.

    focal_mm, x_mm and y_mm are in millimetres; x_mm and y_mm are the offset
    from the sensor centre. Returns the brightness fraction
    1 / (1 + (r / focal_mm) ** 2) ** 2 (equal to cos(atan(r / f)) ** 4),
    unitless, in (0, 1], where r = hypot(x_mm, y_mm).
    """
    f = require_positive("focal_mm", focal_mm)
    x = require_finite("x_mm", x_mm)
    y = require_finite("y_mm", y_mm)
    r = math.hypot(x, y)
    return 1.0 / (1.0 + (r / f) ** 2) ** 2


def natural_vignette_px(
    focal_mm,
    px,
    py,
    sensor_width_mm,
    width_px,
    height_px,
    cx=None,
    cy=None,
):
    """Cos^4 natural vignetting brightness at a pixel position.

    px, py, cx, cy, width_px and height_px are in pixels; focal_mm and
    sensor_width_mm are in millimetres. cx and cy default to (width_px - 1) / 2
    and (height_px - 1) / 2. Each pixel is sensor_width_mm / width_px
    millimetres wide. Returns the brightness fraction, unitless, in (0, 1].
    """
    sensor_width = require_positive("sensor_width_mm", sensor_width_mm)
    px = require_finite("px", px)
    py = require_finite("py", py)
    cx, cy = _principal_point(width_px, height_px, cx, cy)
    mm_per_px = sensor_width / width_px
    return natural_vignette(focal_mm, (px - cx) * mm_per_px, (py - cy) * mm_per_px)


def brightness_to_stops(brightness):
    """Convert a brightness fraction to photographic stops.

    brightness is a unitless fraction greater than 0 (1.0 is full
    brightness). Returns log2(brightness) in stops: 0 for 1.0, negative when
    darker.
    """
    return math.log2(require_positive("brightness", brightness))
