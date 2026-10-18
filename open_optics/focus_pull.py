"""Focus pulls. Frames are unitless; distances are in millimetres."""

import math

from open_optics.validation import require_finite, require_positive_or_inf


def focus_at_frame(keyframes, frame):
    """Return the focus distance in millimetres at a frame of a focus pull.

    keyframes is a list of (frame, focus_mm) pairs: frames are unitless and
    focus_mm is the focus distance in millimetres (math.inf is allowed and
    means 0 diopters). Frames must be strictly increasing and there must be at
    least two keyframes. Focus is interpolated linearly in diopters
    (1000 / focus_mm) between the surrounding keyframes and clamped to the
    first or last keyframe outside the range. Returns a float in millimetres,
    math.inf when the interpolated diopters are 0. Raises ValueError for fewer
    than two keyframes, unsorted frames or repeated frames.
    """
    frame = require_finite("frame", frame)
    points = []
    for i, (key_frame, focus_mm) in enumerate(keyframes):
        points.append((
            require_finite(f"keyframes[{i}] frame", key_frame),
            require_positive_or_inf(f"keyframes[{i}] focus_mm", focus_mm),
        ))
    if len(points) < 2:
        raise ValueError("keyframes needs at least two keyframes")
    for (f0, _), (f1, _) in zip(points, points[1:]):
        if f1 == f0:
            raise ValueError(f"keyframe frames must not be repeated, got {f0} twice")
        if f1 < f0:
            raise ValueError(f"keyframe frames must be sorted in increasing order, got {f0} before {f1}")

    if frame <= points[0][0]:
        return points[0][1]
    if frame >= points[-1][0]:
        return points[-1][1]

    for (f0, m0), (f1, m1) in zip(points, points[1:]):
        if frame == f1:
            return m1
        if f0 <= frame < f1:
            d0 = 0.0 if math.isinf(m0) else 1000.0 / m0
            d1 = 0.0 if math.isinf(m1) else 1000.0 / m1
            diopters = d0 + (d1 - d0) * (frame - f0) / (f1 - f0)
            return math.inf if diopters <= 0 else 1000.0 / diopters
