"""Depth of field helpers for the Open Optics nodes (any torch device)."""

import math

import torch

from open_optics import coc
from open_optics_nodes.dof_blur import blur_layer


def sanitize_depth(depth_m, far_m=1000.0):
    """Return depth in metres as float32 with bad values replaced by far_m.

    depth_m is a float tensor of subject distances in metres. NaN, +inf, -inf
    and values <= 0 become far_m (metres, default 1000.0); every other value is
    unchanged. The result has the same shape as depth_m.
    """
    depth = depth_m.to(torch.float32)
    bad = ~torch.isfinite(depth) | (depth <= 0)
    return torch.where(bad, torch.full_like(depth, far_m), depth)


def coc_radius_map(depth_m, focal_mm, f_number, focus_m, sensor_width_mm, max_radius_px):
    """Return the circle-of-confusion radius map in pixels as float32.

    depth_m is a float tensor [B, H, W] of subject distances in metres (clamped
    to at least 1e-3 m); focal_mm and sensor_width_mm are in millimetres,
    focus_m is the focus distance in metres and f_number is unitless. The image
    width in pixels is depth_m.shape[-1]. The result has the same shape as
    depth_m, holds the blur radius in pixels and is capped at max_radius_px.
    """
    depth = sanitize_depth(depth_m).clamp(min=1e-3)
    width = depth.shape[-1]
    uniq, inverse = torch.unique(depth, return_inverse=True)
    radii = []
    for d in uniq.tolist():
        blur_mm = coc.blur_diameter_mm(focal_mm, f_number, focus_m * 1000.0, d * 1000.0)
        radii.append(coc.blur_radius_px(blur_mm, width, sensor_width_mm, max_px=max_radius_px))
    table = torch.tensor(radii, dtype=torch.float32).to(depth.device)
    return table[inverse.reshape(-1)].reshape(depth.shape)


SHARP_RADIUS_PX = 0.5


def _side_layers(radius, side, width):
    """Split one side (near or far) of the frame into masks by blur radius.

    radius is the float32 [B, H, W] blur radius in pixels and side a bool mask
    of the pixels on this side, all with radius >= SHARP_RADIUS_PX. The side's
    radius range [SHARP_RADIUS_PX, max] is split into equal bins about width
    pixels wide (at least one). Returns the non-empty bin masks, smallest
    radius first.
    """
    if not side.any():
        return []
    extent = radius[side].max().item() - SHARP_RADIUS_PX
    if extent <= 0.0 or width <= 0.0:
        return [side]
    count = max(1, math.ceil(extent / width - 1e-6))
    idx = ((radius - SHARP_RADIUS_PX) / extent * count).floor().long().clamp(0, count - 1)
    masks = [side & (idx == b) for b in range(count)]
    return [m for m in masks if m.any()]


def composite_layers(image_linear, depth_m, radius_map, n_layers, focus_m):
    """Blur signed CoC layers and composite them back to front; returns float32 [B, H, W, 3].

    image_linear is float32 [B, H, W, 3] in linear light; depth_m (metres) and
    radius_map (pixels) are float32 [B, H, W]; focus_m is the focus distance in
    metres. Pixels with a radius below 0.5 px form one in-focus layer that is
    never blurred. The rest are split by sign, far (depth >= focus_m) or near,
    and quantised by radius: the near and far radius ranges share n_layers bins
    of equal width in pixels, each non-empty side getting at least one, and
    empty bins are skipped. Each layer's premultiplied colour and alpha are
    blurred with its mean radius in pixels, then composited with "over" from
    back to front: far layers from largest radius to smallest, the in-focus
    layer, then near layers from smallest radius to largest. The result is
    clamped to 0..1.
    """
    image = image_linear.to(torch.float32)
    depth = sanitize_depth(depth_m)
    radius = radius_map.to(torch.float32)
    sharp = radius < SHARP_RADIUS_PX
    far = ~sharp & (depth >= focus_m)
    near = ~sharp & ~far
    extents = [radius[s].max().item() - SHARP_RADIUS_PX for s in (near, far) if s.any()]
    width = sum(extents) / max(n_layers, 1)
    layers = (list(reversed(_side_layers(radius, far, width))) + [sharp]
              + _side_layers(radius, near, width))
    chw = image.permute(0, 3, 1, 2)
    out = torch.zeros_like(chw)
    cov = torch.zeros_like(chw[:, :1])
    for mask in layers:
        if not mask.any():
            continue
        alpha = mask.to(torch.float32)[:, None]
        layer_radius = 0.0 if mask is sharp else radius[mask].mean().item()
        colour_b = blur_layer(chw * alpha, layer_radius)
        alpha_b = blur_layer(alpha, layer_radius)
        out = colour_b + out * (1.0 - alpha_b)
        cov = alpha_b + cov * (1.0 - alpha_b)
    out = out / cov.clamp_min(1e-8)
    return out.permute(0, 2, 3, 1).clamp(0.0, 1.0).contiguous()
