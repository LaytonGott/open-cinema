"""Shared image helpers for the Open Optics nodes (CPU torch tensors, [B, H, W, C], 0-1)."""

import torch


def check_image(image):
    """Validate a ComfyUI IMAGE: a float32 torch tensor of shape [B, H, W, C].

    Values are unitless, 0 to 1. Returns the image unchanged.
    Raises ValueError if it is not a float32 tensor with 4 dimensions.
    """
    if not isinstance(image, torch.Tensor):
        raise ValueError("image must be a torch tensor")
    if image.dtype != torch.float32:
        raise ValueError(f"image must be float32, got {image.dtype}")
    if image.dim() != 4:
        raise ValueError(f"image must have 4 dims [B,H,W,C], got {image.dim()}")
    return image


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
        raise ValueError("Exactly one of depth_mask or depth_image is needed")
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
