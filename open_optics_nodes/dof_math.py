"""Depth of field helpers for the Open Optics nodes (CPU only)."""

import torch

from open_optics import coc
from open_optics_nodes.dof_blur import blur_layer


def coc_radius_map(depth_m, focal_mm, f_number, focus_m, sensor_width_mm, max_radius_px):
    """Return the circle-of-confusion radius map in pixels as float32.

    depth_m is a float tensor [B, H, W] of subject distances in metres (clamped
    to at least 1e-3 m); focal_mm and sensor_width_mm are in millimetres,
    focus_m is the focus distance in metres and f_number is unitless. The image
    width in pixels is depth_m.shape[-1]. The result has the same shape as
    depth_m, holds the blur radius in pixels and is capped at max_radius_px.
    """
    depth = depth_m.to(torch.float32).clamp(min=1e-3)
    width = depth.shape[-1]
    uniq, inverse = torch.unique(depth, return_inverse=True)
    radii = []
    for d in uniq.tolist():
        blur_mm = coc.blur_diameter_mm(focal_mm, f_number, focus_m * 1000.0, d * 1000.0)
        radii.append(coc.blur_radius_px(blur_mm, width, sensor_width_mm, max_px=max_radius_px))
    table = torch.tensor(radii, dtype=torch.float32)
    return table[inverse.reshape(-1)].reshape(depth.shape)


def composite_layers(image_linear, depth_m, radius_map, n_layers):
    """Blur depth layers and composite them back to front; returns float32 [B, H, W, 3].

    image_linear is float32 [B, H, W, 3] in linear light; depth_m (metres) and
    radius_map (pixels) are float32 [B, H, W]. The range [min, max] of depth_m
    over the whole batch is split into n_layers equal bins (a constant depth
    gives one layer) and empty bins are skipped. Each layer's premultiplied
    colour and alpha are blurred with its mean radius in pixels, then composited
    from the farthest bin to the nearest. The result is clamped to 0..1.
    """
    image = image_linear.to(torch.float32)
    depth = depth_m.to(torch.float32)
    radius = radius_map.to(torch.float32)
    d_min = depth.min().item()
    d_max = depth.max().item()
    if d_max > d_min and n_layers > 1:
        idx = ((depth - d_min) / (d_max - d_min) * n_layers).floor().long()
        idx = idx.clamp(0, n_layers - 1)
    else:
        idx = torch.zeros_like(depth, dtype=torch.long)
    chw = image.permute(0, 3, 1, 2)
    out = torch.zeros_like(chw)
    cov = torch.zeros_like(chw[:, :1])
    for b in range(max(n_layers, 1) - 1, -1, -1):
        mask = idx == b
        if not mask.any():
            continue
        alpha = mask.to(torch.float32)[:, None]
        layer_radius = radius[mask].mean().item()
        colour_b = blur_layer(chw * alpha, layer_radius)
        alpha_b = blur_layer(alpha, layer_radius)
        out = colour_b + out * (1.0 - alpha_b)
        cov = alpha_b + cov * (1.0 - alpha_b)
    out = out / cov.clamp_min(1e-8)
    return out.permute(0, 2, 3, 1).clamp(0.0, 1.0).contiguous()
