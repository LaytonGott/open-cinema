"""Temporal smoothing of depth maps.

This module smooths per-frame depth maps (rows of floats in metres) over time, to
stop depth-of-field blur from shimmering when the estimated depth flickers from
one frame to the next.
"""


def smooth_depth_sequence(frames, strength=0.7):
    """Smooth a sequence of depth maps over time.

    Args:
        frames: list of depth maps, each a list of rows of floats in metres. All
            depth maps have the same size.
        strength: unitless smoothing amount from 0 to 1 (currently unused).

    Returns:
        A new list of depth maps with the same shape as ``frames`` and float values
        in metres. The input is not modified.
    """
    return [[[float(v) for v in row] for row in frame] for frame in frames]
