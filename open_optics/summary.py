"""Text summaries of lens setups. Units: lengths in millimetres (mm) or metres (m), angles in degrees (deg)."""

import math


def _fmt(value):
    """Format a number for display.

    value is a unitless float (the caller's unit applies). Returns 'inf' for
    math.inf, otherwise the value as a string with 2 decimals, e.g. '39.60'.
    """
    if value == math.inf:
        return "inf"
    return f"{value:.2f}"
