"""Brown-Conrady lens distortion.

Coordinates are unitless lens-relative or frame-fraction positions.
"""

import math

from open_optics.pixels import lens_to_pixel, pixel_to_lens
from open_optics.validation import require_finite


class DistortionError(ValueError):
    """Raised when a distortion cannot be inverted."""


def _terms(px, py, c1, c2, c3, t1, t2):
    """Return (radial, dx, dy) Brown-Conrady terms for unitless x, y."""
    r2 = px * px + py * py
    radial = 1 + c1 * r2 + c2 * r2**2 + c3 * r2**3
    dx = 2 * t1 * px * py + t2 * (r2 + 2 * px * px)
    dy = t1 * (r2 + 2 * py * py) + 2 * t2 * px * py
    return radial, dx, dy


def distort_point(x, y, k1=0.0, k2=0.0, k3=0.0, p1=0.0, p2=0.0):
    """Apply Brown-Conrady distortion to a point.

    All arguments are unitless: x and y are lens-relative or frame-fraction
    positions, k1..k3 are radial coefficients and p1, p2 are tangential
    coefficients. Returns an (x_d, y_d) tuple of floats in the same unitless
    frame fractions. Zero coefficients return the input unchanged.
    """
    px = require_finite("x", x)
    py = require_finite("y", y)
    c1 = require_finite("k1", k1)
    c2 = require_finite("k2", k2)
    c3 = require_finite("k3", k3)
    t1 = require_finite("p1", p1)
    t2 = require_finite("p2", p2)

    radial, dx, dy = _terms(px, py, c1, c2, c3, t1, t2)
    return (float(px * radial + dx), float(py * radial + dy))


def undistort_point(x_d, y_d, k1=0.0, k2=0.0, k3=0.0, p1=0.0, p2=0.0,
                    max_iterations=200, tolerance=1e-12):
    """Invert Brown-Conrady distortion by fixed-point iteration.

    All arguments are unitless: x_d and y_d are distorted lens-relative or
    frame-fraction positions, k1..k3 are radial and p1, p2 tangential
    coefficients. Iteration stops when the change is below tolerance (unitless).
    Returns an (x, y) tuple of floats in unitless frame fractions. Raises
    DistortionError if it could not undistort the point.
    """
    qx = require_finite("x_d", x_d)
    qy = require_finite("y_d", y_d)
    c1 = require_finite("k1", k1)
    c2 = require_finite("k2", k2)
    c3 = require_finite("k3", k3)
    t1 = require_finite("p1", p1)
    t2 = require_finite("p2", p2)
    limit = int(require_finite("max_iterations", max_iterations))
    tol = require_finite("tolerance", tolerance)

    px, py = qx, qy
    for _ in range(limit):
        try:
            radial, dx, dy = _terms(px, py, c1, c2, c3, t1, t2)
            if not radial > 0:
                raise DistortionError(
                    "could not undistort point: radial factor became <= 0")
            nx = (qx - dx) / radial
            ny = (qy - dy) / radial
        except OverflowError:
            raise DistortionError(
                "could not undistort point: values overflowed") from None
        if not (math.isfinite(nx) and math.isfinite(ny)):
            raise DistortionError(
                "could not undistort point: values became non-finite")
        done = abs(nx - px) < tol and abs(ny - py) < tol
        px, py = nx, ny
        if done:
            return (float(px), float(py))
    raise DistortionError(
        "could not undistort point: iteration did not converge")


def distort_pixel(px, py, sensor, lens, width_px, height_px,
                  k1=0.0, k2=0.0, k3=0.0, p1=0.0, p2=0.0, cx=None, cy=None):
    """Apply Brown-Conrady distortion to a pixel position.

    px, py, width_px, height_px, cx and cy are in pixels (cx and cy default to
    the image centre); sensor.width_mm and lens.focal_mm are in millimetres;
    k1..k3 and p1, p2 are unitless coefficients. Returns a distorted (px, py)
    tuple of floats in pixels. Zero coefficients return the input unchanged.
    """
    x, y = pixel_to_lens(px, py, width_px, height_px,
                         sensor.width_mm, lens.focal_mm, cx, cy)
    x, y = distort_point(x, y, k1, k2, k3, p1, p2)
    ox, oy = lens_to_pixel(x, y, width_px, height_px,
                           sensor.width_mm, lens.focal_mm, cx, cy)
    return (float(ox), float(oy))


def undistort_pixel(px, py, sensor, lens, width_px, height_px,
                    k1=0.0, k2=0.0, k3=0.0, p1=0.0, p2=0.0, cx=None, cy=None):
    """Invert Brown-Conrady distortion for a pixel position.

    px, py, width_px, height_px, cx and cy are in pixels (cx and cy default to
    the image centre); sensor.width_mm and lens.focal_mm are in millimetres;
    k1..k3 and p1, p2 are unitless coefficients. Returns an undistorted
    (px, py) tuple of floats in pixels. Raises DistortionError if the point
    could not be undistorted.
    """
    x, y = pixel_to_lens(px, py, width_px, height_px,
                         sensor.width_mm, lens.focal_mm, cx, cy)
    x, y = undistort_point(x, y, k1, k2, k3, p1, p2)
    ox, oy = lens_to_pixel(x, y, width_px, height_px,
                           sensor.width_mm, lens.focal_mm, cx, cy)
    return (float(ox), float(oy))


def border_free_zoom(sensor, lens, width_px, height_px,
                     k1=0.0, k2=0.0, k3=0.0, p1=0.0, p2=0.0, cx=None, cy=None,
                     samples=64, max_zoom=10.0):
    """Find the zoom that removes empty borders from an undistorted image.

    An undistorted output pixel at u samples the source at distort(u / z),
    where the division scales lens-relative coordinates about the principal
    point. Returns the smallest z >= 1 (a unitless scale factor, float) such
    that every border pixel centre of the output image, with `samples` points
    along each of the four edges from pixel 0 to width_px - 1 / height_px - 1
    (pixels), lands inside the source pixel-centre range [0, width_px - 1] x
    [0, height_px - 1] (tolerance 1e-9 pixels). z is found by bisection
    between 1.0 and max_zoom (unitless); 1.0 is returned at once if z = 1
    already works, so zero coefficients give exactly 1.0. sensor.width_mm and
    lens.focal_mm are in millimetres; k1..k3 and p1, p2 are unitless; cx and
    cy default to the image centre. Raises DistortionError (message contains
    'no border-free zoom') if max_zoom does not suffice.
    """
    count = max(int(require_finite("samples", samples)), 2)
    top = require_finite("max_zoom", max_zoom)
    w1 = width_px - 1
    h1 = height_px - 1
    points = []
    for i in range(count):
        t = i / (count - 1)
        points += [(t * w1, 0.0), (t * w1, float(h1)),
                   (0.0, t * h1), (float(w1), t * h1)]
    tol = 1e-9

    def works(z):
        for u, v in points:
            x, y = pixel_to_lens(u, v, width_px, height_px,
                                 sensor.width_mm, lens.focal_mm, cx, cy)
            x, y = distort_point(x / z, y / z, k1, k2, k3, p1, p2)
            sx, sy = lens_to_pixel(x, y, width_px, height_px,
                                   sensor.width_mm, lens.focal_mm, cx, cy)
            if not (-tol <= sx <= w1 + tol and -tol <= sy <= h1 + tol):
                return False
        return True

    if works(1.0):
        return 1.0
    if not works(top):
        raise DistortionError(
            "no border-free zoom found up to max_zoom=%r" % (max_zoom,))
    lo, hi = 1.0, top
    for _ in range(50):
        mid = (lo + hi) / 2
        if works(mid):
            hi = mid
        else:
            lo = mid
    return float(hi)
