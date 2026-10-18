"""Temporal smoothing of depth maps.

This module smooths per-frame depth maps (rows of floats in metres) over time, to
stop depth-of-field blur from shimmering when the estimated depth flickers from
one frame to the next.

Method: each pixel keeps a running estimate of its depth over time. Every new valid
depth is blended into the estimate with a gain derived from the strength (higher
strength means a smaller gain and a steadier result). All depths are in metres.

Values that are missing (nan, inf, zero, negative) never enter the estimate. A one-frame
spike (more than 2.5x or less than 0.4x the estimate) is ignored. A persistent
change of two frames or more is accepted at once.

smooth_depth_sequence returns a new list with the same shape as its input, holding
floats in metres; the input is left untouched.

Tip: smooth the depth first with this module, then feed the result to the
DepthOfField node for blur.
"""


import math

from open_optics.validation import require_finite

_NEVER_VALID_DEPTH_M = 1.0  # metres; output for a pixel with no valid depth in any frame


def _require_strength(value):
    """Check a smoothing strength (unitless) and return it as a float.

    Raises ValueError if it is not a finite number or is outside 0 to 1.
    """
    strength = require_finite("strength", value)
    if not 0 <= strength <= 1:
        raise ValueError(f"strength must be between 0 and 1, got {value!r}")
    return strength


def _is_valid(value):
    """Return True if a depth value (metres) is finite and positive, else False."""
    return math.isfinite(value) and value > 0


def _is_outlier(value, est):
    """Return True if a depth value is a spike relative to the estimate.

    Both value and est are in metres, est > 0. A spike is value > 2.5 * est or
    value < 0.4 * est.
    """
    return value > 2.5 * est or value < 0.4 * est


def _validate_frames(frames):
    """Check that frames is a list of equally sized depth maps of numbers (metres).

    Raises ValueError naming the frame and row index if frames, a frame or a row is
    not a list, if rows differ in length, if a frame's height or width differs from
    frame 0, or if an entry is not an int or float (bool and str are rejected;
    nan, inf, zero and negatives are allowed).
    """
    if not isinstance(frames, list):
        raise ValueError(f"frames must be a list, got {type(frames).__name__}")
    size = None
    for i, frame in enumerate(frames):
        if not isinstance(frame, list):
            raise ValueError(f"frame {i} must be a list, got {type(frame).__name__}")
        width = None
        for r, row in enumerate(frame):
            if not isinstance(row, list):
                raise ValueError(
                    f"frame {i} row {r} must be a list, got {type(row).__name__}"
                )
            if width is None:
                width = len(row)
            elif len(row) != width:
                raise ValueError(
                    f"frame {i} row {r} has length {len(row)}, expected {width}"
                )
            for c, v in enumerate(row):
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise ValueError(
                        f"frame {i} row {r} entry {c} must be an int or float, "
                        f"got {v!r}"
                    )
        this_size = (len(frame), width if width is not None else 0)
        if size is None:
            size = this_size
        elif this_size != size:
            raise ValueError(
                f"frame {i} has size {this_size[0]}x{this_size[1]}, "
                f"expected {size[0]}x{size[1]} like frame 0"
            )


def smooth_depth_sequence(frames, strength=0.7):
    """Smooth a sequence of depth maps over time.

    Args:
        frames: list of depth maps, each a list of rows of floats in metres. All
            depth maps have the same size.
        strength: unitless smoothing amount from 0 to 1 (currently unused otherwise).
            Strength 0 returns the input values unchanged (as a float copy). Raises ValueError if it is not a finite number between 0 and 1.

    Values that are missing (nan, inf, zero, negative) never change the running estimate; the
    output for that frame is the current estimate. Leading missing frames are
    backfilled: they output the pixel's first valid value in metres once one appears.
    A pixel that is never valid outputs 1.0 metre (_NEVER_VALID_DEPTH_M) in every frame.

    Spike rejection (a one-frame spike is ignored): a valid value more than 2.5 times or less than 0.4 times the
    current estimate is not blended in; that frame outputs the current estimate.
    The first valid value always initialises the estimate.

    Persistent changes: an outlier is remembered as pending. If the next valid value
    is also an outlier vs the estimate but within 0.4x to 2.5x of the pending value,
    the change is accepted at once: the estimate is set to that value (no easing) and
    it is output. A non-outlier clears pending and blends normally; a missing value
    leaves pending unchanged. The first frame of a change still outputs the old
    estimate.

    Raises:
        ValueError: if strength is invalid, or frames is not a list of equally sized
            lists of rows of int/float entries (bool and str are rejected; nan, inf,
            zero and negatives are allowed). The message names the frame and row.

    Returns:
        A new list of depth maps with the same shape as ``frames`` and float values
        in metres. The input is not modified.
    """
    _require_strength(strength)
    _validate_frames(frames)
    if strength == 0:
        return [[[float(v) for v in row] for row in frame] for frame in frames]
    gain = 1 - 0.9 * strength
    out = [[[0.0] * len(row) for row in frame] for frame in frames]
    for r, row in enumerate(frames[0] if frames else []):
        for c in range(len(row)):
            est = None
            pending = None
            first_t = None
            for t, frame in enumerate(frames):
                v = frame[r][c]
                if _is_valid(v):
                    if est is None:
                        est = float(v)
                    elif not _is_outlier(v, est):
                        pending = None
                        est = est + gain * (v - est)
                    elif pending is not None and not _is_outlier(v, pending):
                        est = float(v)
                        pending = None
                    else:
                        pending = float(v)
                    if first_t is None:
                        first_t = t
                out[t][r][c] = float(v) if est is None else est
            lead = _NEVER_VALID_DEPTH_M if first_t is None else out[first_t][r][c]
            for t in range(len(frames) if first_t is None else first_t):
                out[t][r][c] = lead
    return out
