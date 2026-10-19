"""Shared image helpers for the Open Optics nodes (CPU torch tensors, [B, H, W, C], 0-1)."""

import logging
import math

import torch

LOGGER = logging.getLogger('open_optics_nodes')


def check_image(image):
    """Validate a ComfyUI IMAGE: a float32 torch tensor of shape [B, H, W, C].

    Values are unitless, 0 to 1. Returns the image unchanged.
    Raises ValueError if it is not a float32 tensor with 4 dimensions.
    """
    if not isinstance(image, torch.Tensor):
        raise ValueError(
            f"image must be a float32 torch tensor [B,H,W,C], got {type(image).__name__}")
    if image.dtype != torch.float32:
        raise ValueError(f"image must be float32 [B,H,W,C], got {image.dtype}")
    if image.dim() != 4:
        raise ValueError(f"image must have 4 dims [B,H,W,C], got {image.dim()}")
    return image


def require_positive(name, value):
    """Check that value (in any unit, the caller's) is finite and greater than 0.

    Returns value as a float in the same unit. Raises ValueError naming the
    input and the bad value if value <= 0, NaN or infinite.
    """
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f"{name} must be greater than 0, got {value}")
    return v


def require_choice(name, value, allowed):
    """Check that value (unitless) is one of allowed.

    Returns value unchanged. Raises ValueError naming the input, the allowed
    choices and the bad value otherwise.
    """
    if value not in allowed:
        raise ValueError(f"{name} must be one of {list(allowed)}, got {value!r}")
    return value


CHUNK_FRAMES_INPUT = ('INT', {'default': 8, 'min': 1, 'max': 4096, 'step': 1})


def check_chunk_frames(value):
    """Check that value is a whole number of frames (a unitless count) >= 1.

    Returns int(value). Raises ValueError naming 'chunk_frames' and the bad
    value if it is a bool, a non-integral number, not a number, or < 1.
    """
    ok = not isinstance(value, bool) and isinstance(value, (int, float))
    if ok and isinstance(value, float):
        ok = math.isfinite(value) and value == int(value)
    if not ok or int(value) < 1:
        raise ValueError(f"chunk_frames must be an integer >= 1, got {value!r}")
    return int(value)


def chunk_ranges(total, chunk_frames):
    """Split total frames into (start, stop) frame index pairs.

    total and chunk_frames are counts of frames. The pairs cover range(total)
    in steps of chunk_frames; the last may be shorter. Returns a list of
    (start, stop) tuples, empty when total is 0.
    """
    step = check_chunk_frames(chunk_frames)
    return [(s, min(s + step, total)) for s in range(0, total, step)]


def srgb_to_linear_t(t):
    """Decode sRGB-encoded values (unitless, 0-1) to linear light.

    Input is clamped to 0..1. Returns a tensor of the same shape, 0..1.
    """
    c = t.clamp(0.0, 1.0)
    return torch.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb_t(t):
    """Encode linear-light values (unitless, 0-1) as sRGB.

    Input is clamped to 0..1. Returns a tensor of the same shape, 0..1.
    """
    c = t.clamp(0.0, 1.0)
    hi = 1.055 * c.clamp_min(0.0031308) ** (1 / 2.4) - 0.055
    return torch.where(c <= 0.0031308, c * 12.92, hi)


def _check_colorspace(colorspace):
    if colorspace not in ("srgb", "linear"):
        raise ValueError(f"colorspace must be 'srgb' or 'linear', got {colorspace!r}")


def to_linear(image, colorspace):
    """Convert an image (unitless, 0-1) to linear light.

    colorspace is 'srgb' (decode) or 'linear' (clamp only); anything else
    raises ValueError. Returns a tensor of the same shape, 0..1.
    """
    _check_colorspace(colorspace)
    if colorspace == "srgb":
        return srgb_to_linear_t(image)
    return image.clamp(0.0, 1.0)


def from_linear(image, colorspace):
    """Convert a linear-light image (unitless, 0-1) back to colorspace.

    colorspace is 'srgb' (encode) or 'linear' (clamp only); anything else
    raises ValueError. Returns a tensor of the same shape, 0..1.
    """
    _check_colorspace(colorspace)
    if colorspace == "srgb":
        return linear_to_srgb_t(image)
    return image.clamp(0.0, 1.0)


def finish(image):
    """Replace NaN/inf, clamp to 0..1 and return a contiguous float32 tensor.

    Values are unitless. Returns a tensor of the same shape.
    """
    out = torch.nan_to_num(image, nan=0.0, posinf=1.0, neginf=0.0)
    return out.clamp(0.0, 1.0).to(torch.float32).contiguous()


def resolve_depth(image, depth_mask=None, depth_image=None):
    """Return metric depth as a float32 tensor [B, H, W], in metres.

    Exactly one of depth_mask (MASK [B, H, W]) or depth_image (IMAGE
    [B, H, W, C], averaged over the last dim) must be given; values are used
    as they are, with no clamping, so they may exceed 1. If image is not None,
    the depth batch and H, W must equal the image's (a batch of 1 is not
    broadcast). Raises ValueError otherwise.
    """
    if (depth_mask is None) == (depth_image is None):
        raise ValueError("Exactly one of depth_mask or depth_image must be connected")
    if depth_mask is not None:
        depth = depth_mask.to(torch.float32)
        if depth.dim() != 3:
            raise ValueError(f"depth_mask must have 3 dims [B,H,W], got {depth.dim()}")
    else:
        if depth_image.dim() != 4:
            raise ValueError(f"depth_image must have 4 dims [B,H,W,C], got {depth_image.dim()}")
        depth = depth_image.to(torch.float32).mean(dim=-1)
    if image is not None:
        if depth.shape[0] != image.shape[0]:
            raise ValueError(
                f"depth batch {depth.shape[0]} does not match image batch {image.shape[0]}")
        if depth.shape[1:] != image.shape[1:3]:
            raise ValueError(
                f"depth size {tuple(depth.shape[1:])} does not match image size "
                f"{tuple(image.shape[1:3])}")
    return depth.contiguous()


def log_call(node, tensor_or_device, frames, chunk_frames, seconds, layers=None):
    """Log one INFO record for a node call to the logger 'open_optics_nodes'.

    node is the node key; tensor_or_device is a torch.Tensor or torch.device
    (a device without an index is shown with its index, e.g. the first GPU); frames and chunk_frames are
    counts of frames; seconds is the elapsed time in seconds; layers is an
    optional count of layers, appended only when not None. Returns None.
    """
    dev = tensor_or_device.device if isinstance(tensor_or_device, torch.Tensor) \
        else tensor_or_device
    dev = torch.device(dev)
    if dev.type != "cpu" and dev.index is None:
        dev = torch.empty(0, device=dev).device
    msg = (f"node={node} device={dev} frames={frames} "
           f"chunk_frames={chunk_frames} seconds={seconds:.3f}")
    if layers is not None:
        msg += f" layers={layers}"
    LOGGER.info(msg)
