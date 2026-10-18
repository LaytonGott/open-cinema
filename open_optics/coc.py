"""Circle of confusion (acceptable blur circle) for a sensor."""

import math

from open_optics.validation import require_positive, require_positive_or_inf


def coc_for_sensor(width_mm, height_mm, standard=1500, user_value_mm=None, squeeze=1.0):
    """Return the acceptable blur circle diameter in millimetres.

    width_mm and height_mm are the sensor (gate) dimensions in millimetres.
    If user_value_mm (millimetres) is given it must be positive and is
    returned as given. Otherwise standard must be 1500 or 1730 (Zeiss) and
    the result is the desqueezed diagonal, hypot(width_mm * squeeze,
    height_mm), divided by standard, in millimetres. squeeze is the
    anamorphic squeeze factor (unitless, positive).
    """
    if user_value_mm is not None:
        return require_positive("user_value_mm", user_value_mm)
    if standard not in (1500, 1730):
        raise ValueError(f"standard must be 1500 or 1730, got {standard}")
    squeeze = require_positive("squeeze", squeeze)
    width_mm = require_positive("width_mm", width_mm)
    height_mm = require_positive("height_mm", height_mm)
    return math.hypot(width_mm * squeeze, height_mm) / standard


def coc_for_sensor_obj(sensor, standard=1500, squeeze=1.0):
    """Return the acceptable blur circle diameter in millimetres for a Sensor.

    sensor is an open_optics.sensor.Sensor with dimensions in millimetres. If
    sensor.coc_mm (millimetres) is set it is returned; otherwise the result
    is coc_for_sensor(sensor.width_mm, sensor.height_mm, standard=standard,
    squeeze=squeeze), in millimetres.
    """
    return coc_for_sensor(
        sensor.width_mm,
        sensor.height_mm,
        standard=standard,
        user_value_mm=sensor.coc_mm,
        squeeze=squeeze,
    )


def blur_diameter_mm(focal_mm, f_number, focus_mm, subject_mm):
    """Return the signed blur circle diameter on the sensor in millimetres.

    focal_mm is the focal length, focus_mm the focus distance and subject_mm
    the subject distance, all in millimetres (subject_mm may be math.inf);
    f_number is unitless. The magnitude is f^2 / (N * (s - f)) * (d - s) / d
    with s = focus_mm and d = subject_mm, or f^2 / (N * (s - f)) for an
    infinite subject distance. The sign is negative for a subject in front of
    the focus distance, positive behind it and 0 when it is in focus.
    Raises ValueError if focus_mm <= focal_mm.
    """
    focal_mm = require_positive("focal_mm", focal_mm)
    f_number = require_positive("f_number", f_number)
    focus_mm = require_positive("focus_mm", focus_mm)
    subject_mm = require_positive_or_inf("subject_mm", subject_mm)
    if focus_mm <= focal_mm:
        raise ValueError(
            f"focus_mm must be greater than focal_mm, got focus_mm={focus_mm} "
            f"and focal_mm={focal_mm}"
        )
    scale = focal_mm**2 / (f_number * (focus_mm - focal_mm))
    if math.isinf(subject_mm):
        return scale
    return scale * (subject_mm - focus_mm) / subject_mm
