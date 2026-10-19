"""Framing helpers: sensor geometry derived from the image size.

Lengths are in millimetres and image sizes are in pixels. Standard library
only.
"""

import math  # noqa: F401

from open_optics import validation


def _positive(name, value):
    """Return value as a float if it is a finite number greater than 0.

    Raises ValueError, naming the argument, for every bad value, including
    non-numbers such as bool or str (validation raises TypeError for those).
    """
    try:
        return validation.require_positive(name, value)
    except TypeError as error:
        raise ValueError(str(error)) from error


def sensor_height_mm(sensor_width_mm, image_width_px, image_height_px):
    """Return the sensor height in millimetres for an image of the given size.

    sensor_width_mm is the sensor width in millimetres; image_width_px and
    image_height_px are the image size in pixels. Pixels are assumed square, so
    the height is sensor_width_mm * image_height_px / image_width_px.
    Raises ValueError if any argument is not a finite number greater than 0.
    """
    width_mm = _positive("sensor_width_mm", sensor_width_mm)
    width_px = _positive("image_width_px", image_width_px)
    height_px = _positive("image_height_px", image_height_px)
    return width_mm * height_px / width_px


def subject_distance_m(focal_mm, sensor_height_mm, subject_height_px,
                       image_height_px, real_height_m=1.7):
    """Return the estimated camera-to-subject distance in metres.

    focal_mm and sensor_height_mm are in millimetres; subject_height_px and
    image_height_px are in pixels; real_height_m is the real subject height in
    metres (default 1.7). The subject's height on the sensor is
    h = sensor_height_mm * subject_height_px / image_height_px, and the
    thin-lens relation u = f * (1 + H / h) gives the distance. The result is an
    estimate because real heights vary.
    Raises ValueError if any argument is not a finite number greater than 0.
    """
    focal = _positive("focal_mm", focal_mm)
    sensor = _positive("sensor_height_mm", sensor_height_mm)
    subject_px = _positive("subject_height_px", subject_height_px)
    image_px = _positive("image_height_px", image_height_px)
    real_m = _positive("real_height_m", real_height_m)
    h = sensor * subject_px / image_px
    return focal * (1 + real_m * 1000 / h) / 1000


def subject_height_px(focal_mm, sensor_height_mm, image_height_px, distance_m,
                      real_height_m=1.7):
    """Return the estimated subject height in pixels.

    focal_mm and sensor_height_mm are in millimetres; image_height_px is in
    pixels; distance_m and real_height_m are in metres (real_height_m defaults
    to 1.7). The thin-lens relation gives the height on the sensor in
    millimetres, h = f * H / (u - f), which is scaled by
    image_height_px / sensor_height_mm to pixels. The result is an estimate
    because real heights vary.
    Raises ValueError if any argument is not a finite number greater than 0, or
    if distance_m is not greater than the focal length.
    """
    focal = _positive("focal_mm", focal_mm)
    sensor = _positive("sensor_height_mm", sensor_height_mm)
    image_px = _positive("image_height_px", image_height_px)
    distance = _positive("distance_m", distance_m)
    real_m = _positive("real_height_m", real_height_m)
    if distance * 1000 <= focal:
        raise ValueError(
            f"distance_m must be greater than the focal length, got {distance_m}"
        )
    h = focal * real_m * 1000 / (distance * 1000 - focal)
    return h * image_px / sensor
