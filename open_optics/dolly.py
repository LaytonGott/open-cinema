"""Dolly zoom. Focal lengths are in millimetres, distances in metres."""

from open_optics.validation import require_positive


def dolly_zoom_focal(start_focal_mm, start_distance_m, distance_m):
    """Return the focal length in millimetres that keeps the subject the same size.

    start_focal_mm is the starting focal length in millimetres, and
    start_distance_m and distance_m are the starting and new camera-to-subject
    distances in metres. Computed as start_focal_mm * distance_m /
    start_distance_m. Raises ValueError if any argument is zero, negative or
    not finite.
    """
    f = require_positive("start_focal_mm", start_focal_mm)
    d0 = require_positive("start_distance_m", start_distance_m)
    d = require_positive("distance_m", distance_m)
    return f * d / d0


def dolly_zoom_path(start_focal_mm, start_distance_m, distances_m):
    """Return the dolly zoom focal lengths in millimetres, one per distance.

    start_focal_mm is in millimetres, start_distance_m and each entry of
    distances_m are in metres. Each result is dolly_zoom_focal for that
    distance. Returns a list of floats in millimetres with the same length as
    distances_m. Raises ValueError for any invalid value.
    """
    return [
        dolly_zoom_focal(start_focal_mm, start_distance_m, d) for d in distances_m
    ]
