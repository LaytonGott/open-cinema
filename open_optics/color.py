"""Colour encoding conversions: unitless values 0-1."""

from open_optics.validation import require_finite


def _unit_interval(name, value):
    number = require_finite(name, value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {value}")
    return number


def srgb_to_linear(value):
    """Convert an sRGB-encoded channel value to linear light.

    value is unitless, in [0, 1]. Returns the linear value as a float,
    unitless, in [0, 1]. Raises ValueError outside [0, 1] or if not finite.
    """
    v = _unit_interval("value", value)
    if v <= 0.04045:
        return v / 12.92
    return ((v + 0.055) / 1.055) ** 2.4


def linear_to_srgb(value):
    """Convert a linear-light channel value to sRGB encoding.

    value is unitless, in [0, 1]. Returns the sRGB-encoded value as a float,
    unitless, in [0, 1]. Raises ValueError outside [0, 1] or if not finite.
    """
    v = _unit_interval("value", value)
    if v <= 0.0031308:
        return v * 12.92
    return 1.055 * v ** (1 / 2.4) - 0.055
