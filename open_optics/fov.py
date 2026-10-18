"""Field of view from focal length, sensor size and anamorphic squeeze."""

import math
from dataclasses import dataclass

from open_optics.sensor import Sensor
from open_optics.units import deg_to_rad, rad_to_deg
from open_optics.validation import require_finite, require_positive

_FULL_FRAME_DIAGONAL_MM = 43.2666


@dataclass(frozen=True)
class FieldOfView:
    """Field of view angles (degrees) and full-frame equivalence.

    hfov_deg, vfov_deg and dfov_deg are in degrees; crop_factor is unitless;
    equiv_focal_ff_mm is the full-frame equivalent focal length in millimetres.
    """

    hfov_deg: float
    vfov_deg: float
    dfov_deg: float
    crop_factor: float
    equiv_focal_ff_mm: float


def angle_of_view(focal_mm, dimension_mm):
    """Compute the angle of view across one sensor dimension.

    Args:
        focal_mm: focal length in millimetres.
        dimension_mm: sensor dimension (width, height or diagonal) in millimetres.

    Returns:
        The angle of view in degrees, 2 * atan(dimension / (2 * focal)).
    """
    focal = require_positive("focal_mm", focal_mm)
    dimension = require_positive("dimension_mm", dimension_mm)
    return rad_to_deg(2 * math.atan(dimension / (2 * focal)))


def sensor_angles(focal_mm, sensor):
    """Compute the horizontal, vertical and diagonal angles of view of a sensor.

    Args:
        focal_mm: focal length in millimetres.
        sensor: an open_optics.sensor.Sensor (dimensions in millimetres); no
            anamorphic squeeze is applied.

    Returns:
        A tuple (horizontal_deg, vertical_deg, diagonal_deg) in degrees.
    """
    return (
        angle_of_view(focal_mm, sensor.width_mm),
        angle_of_view(focal_mm, sensor.height_mm),
        angle_of_view(focal_mm, sensor.diagonal_mm),
    )


def focal_from_angle(angle_deg, dimension_mm):
    """Compute the focal length that gives an angle of view across one sensor dimension.

    Args:
        angle_deg: angle of view in degrees, strictly between 0 and 180.
        dimension_mm: sensor dimension (width, height or diagonal) in millimetres.

    Returns:
        The focal length in millimetres, dimension / (2 * tan(angle / 2)).

    Raises:
        ValueError: if angle_deg <= 0 or angle_deg >= 180.
    """
    angle = require_finite("angle_deg", angle_deg)
    dimension = require_positive("dimension_mm", dimension_mm)
    if angle <= 0 or angle >= 180:
        raise ValueError(f"angle_deg must be between 0 and 180 degrees (exclusive), got {angle_deg!r}")
    return dimension / (2 * math.tan(deg_to_rad(angle) / 2))


def field_of_view(focal_mm, sensor_w_mm, sensor_h_mm, squeeze=1.0):
    """Compute the field of view of a lens on a sensor.

    Args:
        focal_mm: focal length in millimetres.
        sensor_w_mm: sensor width in millimetres.
        sensor_h_mm: sensor height in millimetres.
        squeeze: anamorphic squeeze factor (unitless, 1.0 = spherical). The
            horizontal extent is multiplied by it.

    Returns:
        A FieldOfView with horizontal, vertical and diagonal angles in degrees
        (diagonal taken on the desqueezed frame), the crop factor relative to a
        full-frame diagonal of 43.2666 mm, and the full-frame equivalent focal
        length in millimetres.
    """
    focal = require_positive("focal_mm", focal_mm)
    width = require_positive("sensor_w_mm", sensor_w_mm)
    height = require_positive("sensor_h_mm", sensor_h_mm)
    squeeze = require_positive("squeeze", squeeze)

    eff_w = squeeze * width
    diagonal = math.hypot(eff_w, height)
    crop = _FULL_FRAME_DIAGONAL_MM / diagonal

    def fov(d):
        return rad_to_deg(2 * math.atan(d / (2 * focal)))

    return FieldOfView(
        hfov_deg=fov(eff_w),
        vfov_deg=fov(height),
        dfov_deg=fov(diagonal),
        crop_factor=crop,
        equiv_focal_ff_mm=focal * crop,
    )
