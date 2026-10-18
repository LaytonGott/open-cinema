"""Crop factor of a sensor relative to full frame."""

import math

from open_optics.validation import require_positive

FULL_FRAME_DIAGONAL_MM = 43.2666


def crop_factor(width_mm, height_mm):
    """Crop factor of a sensor relative to the 36 x 24 mm full frame.

    Inputs are the sensor width and height in millimetres. Returns the
    unitless float 43.2666 / sqrt(width^2 + height^2). Raises ValueError if
    either dimension is not positive and finite.
    """
    width = require_positive("width_mm", width_mm)
    height = require_positive("height_mm", height_mm)
    return FULL_FRAME_DIAGONAL_MM / math.sqrt(width**2 + height**2)
