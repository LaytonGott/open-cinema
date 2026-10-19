"""Disc (bokeh) blur helpers for Depth of Field (torch tensors on any device)."""

import math

import torch
import torch.nn.functional as F


FFT_MIN_RADIUS_PX = 4.0


def disc_kernel(radius, device=None):
    """Build a normalised disc blur kernel for a radius in pixels.

    Returns a float32 tensor [k, k] with k = 2 * ceil(radius) + 1, created on
    `device` (None means the CPU). Weight is 1 where the distance from the centre
    is <= radius (the centre is always 1), then the kernel is scaled to sum to 1.
    """
    r = math.ceil(radius)
    k = 2 * r + 1
    coords = torch.arange(k, dtype=torch.float32, device=device) - r
    dist2 = coords[:, None] ** 2 + coords[None, :] ** 2
    kernel = (dist2 <= float(radius) ** 2).to(torch.float32)
    kernel[r, r] = 1.0
    return kernel / kernel.sum()


def blur_layer(premult, radius):
    """Blur a float32 [B, C, H, W] tensor with a disc kernel of radius in pixels.

    If radius < 0.5 the input is returned unchanged. Otherwise the image is
    replicate-padded by ceil(radius) and each channel is convolved with the disc.
    Radii >= FFT_MIN_RADIUS_PX (pixels) are convolved with torch.fft.rfft2 / irfft2
    and cropped back to H x W; smaller radii use F.conv2d. Both give the same result.
    Returns a float32 tensor of the same shape [B, C, H, W].
    """
    if radius < 0.5:
        return premult
    c = premult.shape[1]
    h, w = premult.shape[2], premult.shape[3]
    pad = math.ceil(radius)
    kernel = disc_kernel(radius, premult.device).to(premult.dtype)
    padded = F.pad(premult, (pad, pad, pad, pad), mode="replicate")
    if radius >= FFT_MIN_RADIUS_PX:
        hp, wp = padded.shape[2], padded.shape[3]
        k = kernel.shape[0]
        big = torch.zeros(hp, wp, dtype=kernel.dtype, device=kernel.device)
        big[:k, :k] = kernel
        big = torch.roll(big, shifts=(-pad, -pad), dims=(0, 1))
        spec = torch.fft.rfft2(padded) * torch.fft.rfft2(big)
        out = torch.fft.irfft2(spec, s=(hp, wp))
        return out[:, :, pad:pad + h, pad:pad + w].to(premult.dtype).contiguous()
    weight = kernel[None, None].repeat(c, 1, 1, 1)
    return F.conv2d(padded, weight, groups=c)
