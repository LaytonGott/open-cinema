"""Pure progress mapping for the director app (no aiohttp, no SDK)."""

GENERATION_SHARE = 0.85
OPTICS_SHARE = 0.15


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def generation_progress(fraction):
    """Return overall progress, 0 to 0.85, for a generation fraction (0 to 1, clamped)."""
    return GENERATION_SHARE * _clamp(fraction)


def optics_progress(fraction, first_run=True):
    """Return overall progress, 0 to 1: 0.85 + 0.15 * fraction on a first run, else the clamped fraction."""
    fraction = _clamp(fraction)
    if first_run:
        return GENERATION_SHARE + OPTICS_SHARE * fraction
    return fraction


def monotonic(previous, new):
    """Return the larger of the previous and new progress, so progress never falls."""
    return max(previous, new)


def message_for_node(stage, class_type, value=None, maximum=None):
    """Return the human status line (str) for the stage ("generate" or "optics") and running node class type."""
    if stage == "generate":
        if value is not None and maximum is not None:
            return f"Generating video: step {value} of {maximum}"
        return "Generating video"
    if stage == "optics":
        if str(class_type).startswith("DA3"):
            return "Estimating depth"
        if class_type in ("OpenOptics_DepthOfField", "CreateVideo", "SaveVideo"):
            return "Applying depth of field"
    return "Waiting for ComfyUI"
