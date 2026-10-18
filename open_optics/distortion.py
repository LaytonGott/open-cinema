"""Brown-Conrady lens distortion.

Coordinates are unitless lens-relative or frame-fraction positions.
"""

from open_optics.validation import require_finite


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

    r2 = px * px + py * py
    radial = 1 + c1 * r2 + c2 * r2**2 + c3 * r2**3
    x_d = px * radial + 2 * t1 * px * py + t2 * (r2 + 2 * px * px)
    y_d = py * radial + t1 * (r2 + 2 * py * py) + 2 * t2 * px * py
    return (float(x_d), float(y_d))
