"""Conversion between pixel positions and lens-relative coordinates.

Pixel positions start at the centre of the top-left pixel, so the default
principal point of a width_px by height_px image is ((width_px - 1) / 2,
(height_px - 1) / 2). Lens-relative coordinates are unitless (pixels divided
by the focal length in pixels).
"""

from open_optics.validation import require_finite, require_positive


def focal_length_px(focal_mm, sensor_width_mm, width_px):
    """Focal length in pixels.

    focal_mm and sensor_width_mm are in millimetres; width_px is the image
    width in pixels. Returns focal_mm * width_px / sensor_width_mm, in pixels.
    """
    f = require_positive("focal_mm", focal_mm)
    sensor = require_positive("sensor_width_mm", sensor_width_mm)
    width = require_positive("width_px", width_px)
    return f * width / sensor


def _principal_point(width_px, height_px, cx, cy):
    width = require_positive("width_px", width_px)
    height = require_positive("height_px", height_px)
    cx = (width - 1) / 2 if cx is None else require_finite("cx", cx)
    cy = (height - 1) / 2 if cy is None else require_finite("cy", cy)
    return cx, cy


def pixel_to_lens(
    px, py, width_px, height_px, sensor_width_mm, focal_mm, cx=None, cy=None
):
    """Convert a pixel position to unitless lens-relative coordinates.

    px, py, cx, cy and the image size width_px, height_px are in pixels;
    sensor_width_mm and focal_mm are in millimetres. cx and cy default to
    (width_px - 1) / 2 and (height_px - 1) / 2. Returns the tuple
    ((px - cx) / f_px, (py - cy) / f_px), unitless, where f_px is
    focal_length_px(focal_mm, sensor_width_mm, width_px).
    """
    x = require_finite("px", px)
    y = require_finite("py", py)
    cx, cy = _principal_point(width_px, height_px, cx, cy)
    f_px = focal_length_px(focal_mm, sensor_width_mm, width_px)
    return ((x - cx) / f_px, (y - cy) / f_px)


def lens_to_pixel(x, y, width_px, height_px, sensor_width_mm, focal_mm, cx=None, cy=None):
    """Convert unitless lens-relative coordinates to a pixel position.

    x and y are unitless; cx, cy, width_px and height_px are in pixels;
    sensor_width_mm and focal_mm are in millimetres. cx and cy default to
    (width_px - 1) / 2 and (height_px - 1) / 2. Returns the tuple
    (x * f_px + cx, y * f_px + cy) in pixels, where f_px is
    focal_length_px(focal_mm, sensor_width_mm, width_px).
    """
    lx = require_finite("x", x)
    ly = require_finite("y", y)
    cx, cy = _principal_point(width_px, height_px, cx, cy)
    f_px = focal_length_px(focal_mm, sensor_width_mm, width_px)
    return (lx * f_px + cx, ly * f_px + cy)
