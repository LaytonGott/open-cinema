"""Depth of field helpers for the Open Optics nodes (CPU only)."""

import torch

from open_optics import coc


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
