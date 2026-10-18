"""Disc (bokeh) blur helpers for Depth of Field (CPU torch tensors)."""

import math

import torch
import torch.nn.functional as F


def disc_kernel(radius):
    """Build a normalised disc blur kernel for a radius in pixels.

    Returns a float32 tensor [k, k] with k = 2 * ceil(radius) + 1. Weight is 1 where
    the distance from the centre is <= radius (the centre is always 1), then the
    kernel is scaled to sum to 1.
    """
    r = math.ceil(radius)
    k = 2 * r + 1
    coords = torch.arange(k, dtype=torch.float32) - r
    dist2 = coords[:, None] ** 2 + coords[None, :] ** 2
    kernel = (dist2 <= float(radius) ** 2).to(torch.float32)
    kernel[r, r] = 1.0
    return kernel / kernel.sum()


def blur_layer(premult, radius):
    """Blur a float32 [B, C, H, W] tensor with a disc kernel of radius in pixels.

    If radius < 0.5 the input is returned unchanged. Otherwise the image is
    replicate-padded by ceil(radius) and each channel is convolved with the disc.
    Returns a float32 tensor of the same shape [B, C, H, W].
    """
    if radius < 0.5:
        return premult
    c = premult.shape[1]
    pad = math.ceil(radius)
    kernel = disc_kernel(radius).to(premult.dtype)
    weight = kernel[None, None].repeat(c, 1, 1, 1)
    padded = F.pad(premult, (pad, pad, pad, pad), mode="replicate")
    return F.conv2d(padded, weight, groups=c)
