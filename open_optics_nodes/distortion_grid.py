"""Source-pixel grids for lens distortion remapping."""

import torch
import torch.nn.functional as F

from open_optics import distortion, pixels
from open_optics.lens import Lens
from open_optics.sensor import Sensor


def build_source_grid(width_px, height_px, focal_mm, sensor_width_mm,
                      k1, k2, k3, p1, p2, direction, zoom=1.0):
    """Build the source pixel position for every output pixel.

    width_px, height_px and the returned positions are in pixels (0-based,
    u the column, v the row); focal_mm and sensor_width_mm are in
    millimetres; k1, k2, k3, p1, p2 and zoom are unitless. direction 'remove'
    means the output is the undistorted image: the source is
    distort(x / zoom, y / zoom). direction 'apply' means the output is the
    distorted image: the source is undistort(x, y), and zoom is ignored.
    Returns a list of height_px rows, each a list of width_px (sx, sy) float
    tuples in source pixels. Raises ValueError for any other direction.
    """
    if direction not in ("remove", "apply"):
        raise ValueError("direction must be 'remove' or 'apply', got %r" % (direction,))
    grid = []
    for v in range(height_px):
        row = []
        for u in range(width_px):
            x, y = pixels.pixel_to_lens(u, v, width_px, height_px,
                                        sensor_width_mm, focal_mm)
            if direction == "remove":
                x, y = distortion.distort_point(x / zoom, y / zoom,
                                                k1, k2, k3, p1, p2)
            else:
                x, y = distortion.undistort_point(x, y, k1, k2, k3, p1, p2)
            row.append(tuple(float(c) for c in pixels.lens_to_pixel(
                x, y, width_px, height_px, sensor_width_mm, focal_mm)))
        grid.append(row)
    return grid


def crop_zoom(width_px, height_px, focal_mm, sensor_width_mm,
              k1, k2, k3, p1, p2):
    """Find the zoom that removes empty borders after distortion removal.

    width_px and height_px are in pixels; focal_mm and sensor_width_mm are in
    millimetres (the sensor height follows the image aspect ratio); k1, k2,
    k3, p1 and p2 are unitless. Returns the unitless zoom factor as a float.
    """
    sensor = Sensor(sensor_width_mm, sensor_width_mm * height_px / width_px)
    return float(distortion.border_free_zoom(
        sensor, Lens(focal_mm, 1.0, 1.0), width_px, height_px,
        k1, k2, k3, p1, p2))


def sample_bilinear(image, grid_px, outside="border"):
    """Sample an image at source pixel positions with bilinear filtering.

    image is a float32 tensor [B, H, W, C]; grid_px is a float tensor
    [H, W, 2] of (sx, sy) source positions in pixels (0-based, sx the column,
    sy the row), shared by every batch item. outside 'border' (default) makes
    positions outside the image take the nearest border pixel; 'black' sets
    every channel to 0 where (sx, sy) lies outside [0, W-1] x [0, H-1] by more
    than 1e-4 pixels. Returns a float32 tensor [B, H, W, C]. Raises
    ValueError for any other outside value.
    """
    if outside not in ("border", "black"):
        raise ValueError("outside must be 'border' or 'black', got %r" % (outside,))
    b, h, w, _ = image.shape
    sx = grid_px[..., 0].to(torch.float32)
    sy = grid_px[..., 1].to(torch.float32)
    gx = 2.0 * sx / (w - 1) - 1.0 if w > 1 else torch.zeros_like(sx)
    gy = 2.0 * sy / (h - 1) - 1.0 if h > 1 else torch.zeros_like(sy)
    grid = torch.stack([gx, gy], dim=-1).unsqueeze(0).expand(b, -1, -1, -1)
    out = F.grid_sample(image.to(torch.float32).permute(0, 3, 1, 2), grid,
                        mode="bilinear", padding_mode="border",
                        align_corners=True)
    out = out.permute(0, 2, 3, 1).contiguous()
    if outside == "black":
        tol = 1e-4
        valid = ((sx >= -tol) & (sx <= w - 1 + tol)
                 & (sy >= -tol) & (sy <= h - 1 + tol))
        out = out * valid.to(torch.float32)[None, :, :, None]
    return out
