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


_NODE_MESSAGES = {}
for _text, _types in (
    ("Loading the LTX-2 models", (
        "UnetLoaderGGUF", "LTXAVTextEncoderLoader", "VAELoader",
        "LTXVAudioVAELoader", "LatentUpscaleModelLoader", "CLIPTextEncode")),
    ("Upscaling the video", ("LTXVLatentUpsampler",)),
    ("Decoding the video", ("VAEDecodeTiled", "LTXVAudioVAEDecode")),
    ("Reading the video", ("LoadVideo", "GetVideoComponents")),
    ("Estimating depth", ("LoadDA3Model", "DA3Inference", "DA3Render")),
    ("Scaling depth to metres", (
        "OpenOptics_DepthToMetric", "OpenOptics_DepthTemporalSmooth")),
    ("Applying depth of field", ("OpenOptics_DepthOfField",)),
    ("Saving the video", ("CreateVideo", "SaveVideo")),
):
    for _type in _types:
        _NODE_MESSAGES[_type] = _text

_STAGE_DEFAULTS = {"generate": "Generating video", "optics": "Estimating depth"}


def message_for_node(stage, class_type, value=None, maximum=None, previous=None):
    """Return the human status line (str) for the running node `class_type` of `stage` ("generate" or "optics").

    SamplerCustomAdvanced gives "Generating video: step {value} of {maximum}"
    when both are given. An unknown or None class type keeps `previous`
    (None and "Waiting for ComfyUI" do not count), else the stage default.
    Never returns "Waiting for ComfyUI".
    """
    if class_type == "SamplerCustomAdvanced":
        if value is not None and maximum is not None:
            return f"Generating video: step {value} of {maximum}"
        return "Generating video"
    if class_type in _NODE_MESSAGES:
        return _NODE_MESSAGES[class_type]
    if previous is not None and previous != "Waiting for ComfyUI":
        return previous
    return _STAGE_DEFAULTS.get(stage, "Generating video")
