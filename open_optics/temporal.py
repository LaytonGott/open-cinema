"""Temporal smoothing of depth maps.

This module smooths per-frame depth maps (rows of floats in metres) over time, to
stop depth-of-field blur from shimmering when the estimated depth flickers from
one frame to the next.
"""


from open_optics.validation import require_finite


def _require_strength(value):
    """Check a smoothing strength (unitless) and return it as a float.

    Raises ValueError if it is not a finite number or is outside 0 to 1.
    """
    strength = require_finite("strength", value)
    if not 0 <= strength <= 1:
        raise ValueError(f"strength must be between 0 and 1, got {value!r}")
    return strength


def smooth_depth_sequence(frames, strength=0.7):
    """Smooth a sequence of depth maps over time.

    Args:
        frames: list of depth maps, each a list of rows of floats in metres. All
            depth maps have the same size.
        strength: unitless smoothing amount from 0 to 1 (currently unused otherwise).
            Raises ValueError if it is not a finite number between 0 and 1.

    Returns:
        A new list of depth maps with the same shape as ``frames`` and float values
        in metres. The input is not modified.
    """
    _require_strength(strength)
    return [[[float(v) for v in row] for row in frame] for frame in frames]
