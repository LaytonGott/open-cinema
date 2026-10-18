"""Brown-Conrady lens distortion.

Coordinates are unitless lens-relative or frame-fraction positions.
"""

import math

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
