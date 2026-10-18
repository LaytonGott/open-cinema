"""Anamorphic desqueeze helpers."""

from open_optics.validation import require_finite, require_positive


def desqueeze_size(width_px, height_px, squeeze, mode="widen"):
    """Desqueezed image size for an anamorphic squeeze factor.

    width_px and height_px are in pixels; squeeze is the unitless squeeze
    factor. mode 'widen' returns (width_px * squeeze, height_px); mode
    'shorten' returns (width_px, height_px / squeeze). Returns a (width,
    height) tuple of floats in pixels. The results are not rounded; callers
    wanting whole pixels should use round() (Python's built-in, which rounds
    half to even). Raises ValueError if any input is not positive and finite
    or if mode is not 'widen' or 'shorten'.
    """
    width = require_positive("width_px", width_px)
    height = require_positive("height_px", height_px)
    factor = require_positive("squeeze", squeeze)
    if mode == "widen":
        return (float(width * factor), float(height))
    if mode == "shorten":
        return (float(width), float(height / factor))
    raise ValueError(f"mode must be 'widen' or 'shorten', got {mode!r}")


def squeeze_size(width_px, height_px, squeeze, mode="widen"):
    """Squeezed image size, the inverse of desqueeze_size with the same mode.

    width_px and height_px are the desqueezed size in pixels; squeeze is the
    unitless squeeze factor. mode 'widen' returns (width_px / squeeze,
    height_px); mode 'shorten' returns (width_px, height_px * squeeze).
    Returns a (width, height) tuple of unrounded floats in pixels. Raises
    ValueError if any input is not positive and finite or if mode is not
    'widen' or 'shorten'.
    """
    width = require_positive("width_px", width_px)
    height = require_positive("height_px", height_px)
    factor = require_positive("squeeze", squeeze)
    if mode == "widen":
        return (float(width / factor), float(height))
    if mode == "shorten":
        return (float(width), float(height * factor))
    raise ValueError(f"mode must be 'widen' or 'shorten', got {mode!r}")


def desqueeze_point(x, y, squeeze, mode="widen", fractional=False):
    """Desqueezed position of a point in a squeezed frame.

    x and y are pixel positions when fractional is False, or frame fractions
    (0..1 of the frame) when True; squeeze is the unitless squeeze factor. In
    pixels, mode 'widen' returns (x * squeeze, y) and mode 'shorten' returns
    (x, y / squeeze). Frame fractions are unchanged in either mode because the
    frame scales with the point. Returns an (x, y) tuple of floats in the same
    units as the input. Raises ValueError if squeeze is not positive and
    finite, x or y is not finite, or mode is not 'widen' or 'shorten'.
    """
    px = require_finite("x", x)
    py = require_finite("y", y)
    factor = require_positive("squeeze", squeeze)
    if mode not in ("widen", "shorten"):
        raise ValueError(f"mode must be 'widen' or 'shorten', got {mode!r}")
    if fractional:
        return (float(px), float(py))
    if mode == "widen":
        return (float(px * factor), float(py))
    return (float(px), float(py / factor))


def squeeze_point(x, y, squeeze, mode="widen", fractional=False):
    """Squeezed position of a point, the inverse of desqueeze_point.

    x and y are pixel positions in the desqueezed frame when fractional is
    False, or frame fractions (0..1 of the frame) when True; squeeze is the
    unitless squeeze factor. In pixels, mode 'widen' returns (x / squeeze, y)
    and mode 'shorten' returns (x, y * squeeze). Frame fractions are unchanged
    in either mode. Returns an (x, y) tuple of floats in the same units as the
    input. Raises ValueError if squeeze is not positive and finite, x or y is
    not finite, or mode is not 'widen' or 'shorten'.
    """
    px = require_finite("x", x)
    py = require_finite("y", y)
    factor = require_positive("squeeze", squeeze)
    if mode not in ("widen", "shorten"):
        raise ValueError(f"mode must be 'widen' or 'shorten', got {mode!r}")
    if fractional:
        return (float(px), float(py))
    if mode == "widen":
        return (float(px / factor), float(py))
    return (float(px), float(py * factor))


def delivered_aspect_ratio(gate_width_mm, gate_height_mm, squeeze):
    """Aspect ratio of the desqueezed image delivered from a sensor gate.

    gate_width_mm and gate_height_mm are in millimetres; squeeze is the
    unitless anamorphic squeeze factor. Returns the unitless float
    gate_width_mm / gate_height_mm * squeeze. Raises ValueError if any input
    is not positive and finite.
    """
    width = require_positive("gate_width_mm", gate_width_mm)
    height = require_positive("gate_height_mm", gate_height_mm)
    factor = require_positive("squeeze", squeeze)
    return float(width / height * factor)


def bokeh_aspect(squeeze, desqueezed=True):
    """Height-to-width ratio of an out-of-focus highlight.

    squeeze is the unitless anamorphic squeeze factor. Returns the unitless
    float squeeze when desqueezed is True (oval, taller than wide), or 1.0
    when desqueezed is False (the squeezed recording is round). Raises
    ValueError if squeeze is not positive and finite.
    """
    factor = require_positive("squeeze", squeeze)
    return float(factor) if desqueezed else 1.0
