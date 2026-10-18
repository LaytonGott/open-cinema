"""Input validation helpers.

Values are checked and returned as passed (unitless floats; any unit, such as
millimetres, is the caller's convention and is not converted).
"""

import math


def _as_number(name, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"{name} must be a number, got {value!r} ({type(value).__name__})"
        )
    return float(value)


def require_positive(name, value):
    """Check that value is a finite number greater than 0.

    Unitless: the value is not converted (e.g. millimetres stay millimetres).
    Returns the value as a float. Raises TypeError for non-numbers (including
    bool) and ValueError for zero, negatives, NaN or infinity.
    """
    number = _as_number(name, value)
    if math.isnan(number) or math.isinf(number) or number <= 0:
        raise ValueError(f"{name} must be greater than 0 and finite, got {value}")
    return number


def require_positive_or_inf(name, value):
    """Check that value is a number greater than 0, or +infinity.

    Unitless: the value is not converted (e.g. millimetres stay millimetres).
    Returns the value as a float. Raises TypeError for non-numbers (including
    bool) and ValueError for zero, negatives, NaN or -infinity.
    """
    number = _as_number(name, value)
    if math.isnan(number) or number <= 0:
        raise ValueError(f"{name} must be greater than 0, got {value}")
    return number


def require_finite(name, value):
    """Check that value is a finite number (any sign, including zero).

    Unitless: the value is not converted (e.g. millimetres stay millimetres).
    Returns the value as a float. Raises TypeError for non-numbers (including
    bool) and ValueError for NaN or infinity.
    """
    number = _as_number(name, value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite, got {value}")
    return number
