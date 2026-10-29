"""Disc (bokeh) blur helpers for Depth of Field (torch tensors on any device)."""

import math

import torch
import torch.nn.functional as F


FFT_MIN_RADIUS_PX = 4.0


def disc_kernel(radius, device=None, squeeze=1.0):
    """Build a normalised disc (or, with squeeze > 1, tall elliptical) blur kernel for a radius in pixels.

    Returns a float32 tensor [kh, kw] with kh = 2 * ceil(radius) + 1 and
    kw = 2 * ceil(radius / squeeze) + 1, created on `device` (None means the
    CPU). Weight is 1 where (dx * squeeze)^2 + dy^2 <= radius^2 for the pixel
    offset (dx horizontal, dy vertical) from the centre (the centre is always
    1), then the kernel is scaled to sum to 1. squeeze (unitless, >= 1, default
    1.0) makes the bokeh squeeze times taller than wide, as with an anamorphic
    lens; 1.0 is the round disc.
    """
    r = math.ceil(radius)
    rw = math.ceil(radius / squeeze) if squeeze != 1.0 else r
    ys = torch.arange(2 * r + 1, dtype=torch.float32, device=device) - r
    xs = torch.arange(2 * rw + 1, dtype=torch.float32, device=device) - rw
    dist2 = ys[:, None] ** 2 + (xs[None, :] * squeeze) ** 2
    kernel = (dist2 <= float(radius) ** 2).to(torch.float32)
    kernel[r, rw] = 1.0
    return kernel / kernel.sum()


def blur_layer(premult, radius, squeeze=1.0):
    """Blur a float32 [B, C, H, W] tensor with a disc kernel of radius in pixels.

    If radius < 0.5 the input is returned unchanged. Otherwise the image is
    replicate-padded by ceil(radius) and each channel is convolved with the disc.
    Radii >= FFT_MIN_RADIUS_PX (pixels) are convolved with torch.fft.rfft2 / irfft2
    and cropped back to H x W; smaller radii use F.conv2d. Both give the same result.
    Returns a float32 tensor of the same shape [B, C, H, W]. squeeze (>= 1,
    default 1.0) uses the elliptical kernel of disc_kernel, squeeze times taller
    than wide (the horizontal padding is ceil(radius / squeeze)).
    """
    if radius < 0.5:
        return premult
    c = premult.shape[1]
    h, w = premult.shape[2], premult.shape[3]
    pad = math.ceil(radius)
    padx = math.ceil(radius / squeeze) if squeeze != 1.0 else pad
    kernel = (disc_kernel(radius, premult.device) if squeeze == 1.0
              else disc_kernel(radius, premult.device, squeeze)).to(premult.dtype)
    padded = F.pad(premult, (padx, padx, pad, pad), mode="replicate")
    if radius >= FFT_MIN_RADIUS_PX:
        hp, wp = padded.shape[2], padded.shape[3]
        kh, kw = kernel.shape
        big = torch.zeros(hp, wp, dtype=kernel.dtype, device=kernel.device)
        big[:kh, :kw] = kernel
        big = torch.roll(big, shifts=(-pad, -padx), dims=(0, 1))
        spec = torch.fft.rfft2(padded) * torch.fft.rfft2(big)
        out = torch.fft.irfft2(spec, s=(hp, wp))
        return out[:, :, pad:pad + h, padx:padx + w].to(premult.dtype).contiguous()
    weight = kernel[None, None].repeat(c, 1, 1, 1)
    return F.conv2d(padded, weight, groups=c)
