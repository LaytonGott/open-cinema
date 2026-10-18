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


def equivalent_focal_mm(focal_mm, width_mm, height_mm):
    """Full-frame equivalent focal length of a lens on a given sensor.

    Inputs are the focal length, sensor width and sensor height, all in
    millimetres. Returns the equivalent focal length in millimetres as a
    float: focal_mm * crop_factor(width_mm, height_mm). Raises ValueError if
    any input is not positive and finite.
    """
    focal = require_positive("focal_mm", focal_mm)
    return focal * crop_factor(width_mm, height_mm)


def equivalent_f_number(f_number, width_mm, height_mm):
    """Full-frame equivalent f-number of a lens on a given sensor.

    f_number is unitless; sensor width and height are in millimetres.
    Returns the unitless equivalent f-number as a float:
    f_number * crop_factor(width_mm, height_mm). Raises ValueError if any
    input is not positive and finite.
    """
    f = require_positive("f_number", f_number)
    return f * crop_factor(width_mm, height_mm)
