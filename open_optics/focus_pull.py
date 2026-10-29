"""Focus pulls. Frames are unitless; distances are in millimetres (rack_focus_m: metres)."""

import math

from open_optics.validation import require_finite, require_positive, require_positive_or_inf


def rack_focus_m(a_m, b_m, t, start=0.2, end=0.8):
    """Return the focus distance in metres at time t of an eased rack focus from a_m to b_m.

    a_m and b_m are the start and end focus distances in metres (finite, > 0);
    t is the time as a fraction of the clip (0 to 1); start and end (fractions,
    0 <= start < end <= 1) bound the pull. With u = clamp((t - start) / (end -
    start), 0, 1) and the smoothstep s = u^2 (3 - 2u), focus moves linearly in
    diopters: 1 / d = (1 - s) / a_m + s / b_m. Returns metres. Raises
    ValueError for bad distances, t outside [0, 1] or a bad start/end.
    """
    a_m = require_positive("a_m", a_m)
    b_m = require_positive("b_m", b_m)
    t = require_finite("t", t)
    start = require_finite("start", start)
    end = require_finite("end", end)
    if not 0.0 <= t <= 1.0:
        raise ValueError(f"t must be from 0 to 1, got {t}")
    if not 0.0 <= start < end <= 1.0:
        raise ValueError(f"start and end must satisfy 0 <= start < end <= 1, got {start}, {end}")
    u = min(1.0, max(0.0, (t - start) / (end - start)))
    s = u * u * (3.0 - 2.0 * u)
    return 1.0 / ((1.0 - s) / a_m + s / b_m)


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
