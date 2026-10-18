"""Anamorphic desqueeze helpers."""

from open_optics.validation import require_positive


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
