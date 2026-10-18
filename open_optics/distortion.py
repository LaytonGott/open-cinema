"""Brown-Conrady lens distortion.

Point coordinates are unitless normalised image-plane coordinates (x/z, y/z), the same as OpenCV.
"""

import math

from open_optics.pixels import lens_to_pixel, pixel_to_lens
from open_optics.validation import require_finite, require_positive


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

    All arguments are unitless. x and y are
    normalised image-plane coordinates (x/z, y/z), the same as OpenCV.
    The coefficients are unitless and are taken in the order
    (k1, k2, k3, p1, p2); OpenCV uses (k1, k2, p1, p2, k3). For
    OpenCV-ordered vectors use distort_point_opencv or opencv_to_library_coeffs.
    Returns an (x_d, y_d) tuple of floats in the same unitless normalised
    coordinates. Zero coefficients return the input unchanged.
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


def classify_distortion(k1=0.0, k2=0.0, k3=0.0, radius=0.5, tolerance=1e-9):
    """Classify radial distortion at a given radius.

    All arguments are unitless: k1..k3 are radial coefficients, radius is a
    lens-relative distance from the centre (must be > 0) and tolerance is the
    allowed deviation of the radial factor from 1. Returns the string
    'barrel' if the factor 1 + k1*r^2 + k2*r^4 + k3*r^6 is below
    1 - tolerance, 'pincushion' if above 1 + tolerance, else 'neutral'.
    """
    c1 = require_finite("k1", k1)
    c2 = require_finite("k2", k2)
    c3 = require_finite("k3", k3)
    r = require_positive("radius", radius)
    r2 = r * r
    factor = 1 + c1 * r2 + c2 * r2**2 + c3 * r2**3
    if factor < 1 - tolerance:
        return "barrel"
    if factor > 1 + tolerance:
        return "pincushion"
    return "neutral"


def straight_line_deviation(points):
    """Largest distance of points from their best-fit straight line.

    points is a list of at least 2 (x, y) tuples in unitless normalised image-plane coordinates (x/z, y/z), the same as OpenCV.
    The line is fitted by total least squares (centroid and principal axis of
    the 2x2 covariance). Returns the largest perpendicular distance of any
    point from that line as a float in the same unitless normalised image-plane coordinates (x/z, y/z), the same as OpenCV;
    0.0 if all points coincide or the covariance is degenerate. Raises
    ValueError if fewer than 2 points are given.
    """
    pts = [(float(x), float(y)) for x, y in points]
    n = len(pts)
    if n < 2:
        raise ValueError("points must contain at least 2 points")
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - cx) ** 2 for p in pts)
    syy = sum((p[1] - cy) ** 2 for p in pts)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in pts)
    if sxx + syy == 0.0:
        return 0.0
    theta = 0.5 * math.atan2(2 * sxy, sxx - syy)
    dx, dy = math.cos(theta), math.sin(theta)
    return float(max(abs(-(p[0] - cx) * dy + (p[1] - cy) * dx) for p in pts))


def opencv_to_library_coeffs(k1, k2, p1, p2, k3=0.0):
    """Reorder OpenCV distortion coefficients into this library's order.

    All arguments are unitless. OpenCV's order is (k1, k2, p1, p2, k3); the
    library's order is (k1, k2, k3, p1, p2). Each value is checked with
    require_finite. Returns the tuple (k1, k2, k3, p1, p2) as floats.
    """
    c1 = require_finite("k1", k1)
    c2 = require_finite("k2", k2)
    t1 = require_finite("p1", p1)
    t2 = require_finite("p2", p2)
    c3 = require_finite("k3", k3)
    return (float(c1), float(c2), float(c3), float(t1), float(t2))


def distort_point_opencv(x, y, k1, k2, p1, p2, k3=0.0):
    """Distort a point using OpenCV-ordered distortion coefficients.

    x and y are unitless normalised image-plane coordinates (x/z, y/z), the
    same as OpenCV. Coefficients are unitless, in OpenCV order
    (k1, k2, p1, p2, k3). Returns the distorted (x_d, y_d) tuple of floats.
    """
    c1, c2, c3, t1, t2 = opencv_to_library_coeffs(k1, k2, p1, p2, k3)
    return distort_point(x, y, c1, c2, c3, t1, t2)


def undistort_point_opencv(x_d, y_d, k1, k2, p1, p2, k3=0.0):
    """Undistort a point using OpenCV-ordered distortion coefficients.

    x_d and y_d are unitless normalised image-plane coordinates (x/z, y/z),
    the same as OpenCV. Coefficients are unitless, in OpenCV order
    (k1, k2, p1, p2, k3). Returns the undistorted (x, y) tuple of floats.
    Raises DistortionError if it could not undistort.
    """
    c1, c2, c3, t1, t2 = opencv_to_library_coeffs(k1, k2, p1, p2, k3)
    return undistort_point(x_d, y_d, c1, c2, c3, t1, t2)
