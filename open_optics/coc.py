"""Circle of confusion (acceptable blur circle) for a sensor."""

import math

from open_optics.validation import require_positive


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
