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


# How much of a run each node is worth. ComfyUI's own `progress_state` only lists the nodes that have started, so its fraction
# is near 1 from the first node on; the position of the running node in the graph is what tells how far a run is.
_WEIGHTS = {
    "UnetLoaderGGUF": 8, "LTXAVTextEncoderLoader": 8, "CLIPTextEncode": 4, "SamplerCustomAdvanced": 24,
    "LTXVLatentUpsampler": 4, "VAEDecodeTiled": 12, "LTXVAudioVAEDecode": 3,
    "LoadDA3Model": 3, "DA3Inference": 12, "DA3Render": 3, "OpenOptics_DepthToMetric": 3,
    "OpenOptics_DepthTemporalSmooth": 3, "OpenOptics_DepthOfField": 14,
    "CreateVideo": 2, "SaveVideo": 2,
}


def node_fraction(types, current_id, step=None, steps=None):
    """Return how far a run is, 0 to 1, while node `current_id` runs; None if that node is not in the graph.

    `types` is {node id: class type} in the order the graph lists its nodes (about the order they run). Each node has a
    weight (`_WEIGHTS`, 1 for the rest); the fraction is the weight of the nodes before the running one, plus the running
    node's share `step / steps` when both are given, over the total weight.
    """
    ids = list(types)
    current = str(current_id)
    if current not in types:
        return None
    weight = {i: _WEIGHTS.get(types[i], 1) for i in ids}
    total = sum(weight.values())
    before = sum(weight[i] for i in ids[:ids.index(current)])
    partial = 0.0
    if isinstance(step, (int, float)) and isinstance(steps, (int, float)) and steps > 0:
        partial = _clamp(step / steps)
    return _clamp((before + weight[current] * partial) / total)


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
