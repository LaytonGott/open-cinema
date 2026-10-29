"""Depth of Field node for the Open Optics pack (CPU torch tensors)."""

import math
import time

import torch

from open_optics.focus_pull import rack_focus_m
from open_optics_nodes import common
from open_optics_nodes.device import get_device
from open_optics_nodes.dof_math import composite_layers, coc_radius_map

_LAYERS = {"draft": 4, "normal": 8}
_POINT = ("FLOAT", {"default": -1.0, "min": -1.0, "max": 1.0, "step": 0.001})


def _point_on(name, x, y):
    """Return True when the point (x, y) (frame fractions) is set, False when both are negative; ValueError for a mix."""
    if x >= 0 and y >= 0:
        return True
    if x < 0 and y < 0:
        return False
    raise ValueError(f"{name}_x and {name}_y must both be >= 0 (a point) or both negative (off), got {x}, {y}")


def depth_at_point(depth, x, y, fallback_m):
    """Return, per frame, the depth in metres at the frame-fraction point (x, y) as a list of floats.

    depth is a float tensor [B, H, W] in metres. Each value is the median (the
    lower middle value) of the finite, positive depths in a square window of
    side max(3, 2 * round(0.01 * min(H, W)) + 1) pixels centred on pixel
    (round(x * (W - 1)), round(y * (H - 1))), clipped to the frame; a frame
    whose window has no such value gets fallback_m (metres).
    """
    _, h, w = depth.shape
    cx, cy = round(x * (w - 1)), round(y * (h - 1))
    half = max(3, 2 * round(0.01 * min(h, w)) + 1) // 2
    window = depth[:, max(0, cy - half):cy + half + 1, max(0, cx - half):cx + half + 1].reshape(depth.shape[0], -1)
    out = []
    for values in window:
        good = values[torch.isfinite(values) & (values > 0)]
        out.append(float(torch.median(good)) if good.numel() else float(fallback_m))
    return out


class OpenOptics_DepthOfField:
    """Blur an image by layered depth of field from real lens parameters."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "focal_mm": ("FLOAT", {"default": 50.0, "min": 1.0, "max": 1000.0, "step": 0.1}),
                "f_number": ("FLOAT", {"default": 2.8, "min": 0.5, "max": 64.0, "step": 0.1}),
                "focus_m": ("FLOAT", {"default": 3.0, "min": 0.01, "max": 100000.0, "step": 0.1}),
                "sensor_width_mm": ("FLOAT", {"default": 36.0, "min": 1.0, "max": 100.0, "step": 0.1}),
                "quality": (["draft", "normal"], {"default": "normal"}),
                "max_radius_px": ("INT", {"default": 16, "min": 0, "max": 256, "step": 1}),
                "colorspace": (["srgb", "linear"], {"default": "srgb"}),
            },
            "optional": {
                "depth_mask": ("MASK",),
                "depth_image": ("IMAGE",),
                "chunk_frames": common.CHUNK_FRAMES_INPUT,
                "max_layers": ("INT", {"default": 12, "min": 1, "max": 64, "step": 1}),
                "focus_x": _POINT,
                "focus_y": _POINT,
                "rack_x": _POINT,
                "rack_y": _POINT,
                "rack_start": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0, "step": 0.01}),
                "rack_end": ("FLOAT", {"default": 0.8, "min": 0.0, "max": 1.0, "step": 0.01}),
                "bokeh_squeeze": ("FLOAT", {"default": 1.0, "min": 1.0, "max": 2.0, "step": 0.05}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "coc_px")
    FUNCTION = "apply"
    CATEGORY = "Open Optics"

    def apply(self, image, focal_mm=50.0, f_number=2.8, focus_m=3.0, sensor_width_mm=36.0,
              quality="normal", max_radius_px=16, colorspace="srgb",
              depth_mask=None, depth_image=None, chunk_frames=8, max_layers=12,
              focus_x=-1.0, focus_y=-1.0, rack_x=-1.0, rack_y=-1.0, rack_start=0.2, rack_end=0.8,
              bokeh_squeeze=1.0):
        """Apply depth of field blur.

        focal_mm and sensor_width_mm are in millimetres, focus_m is in metres,
        f_number is unitless and max_radius_px is in pixels. Exactly one of
        depth_mask or depth_image (metres) must be connected. Returns a 2-tuple:
        a float32 IMAGE [B, H, W, C] in 0..1, and coc_px, a float32 MASK
        [B, H, W] with the blur radius divided by max_radius_px, clamped to 0..1.
        A max_radius_px of 0 skips blurring: the image is returned unchanged
        with an all-zero coc_px. Raises ValueError for bad inputs, including a
        negative or non-finite max_radius_px. chunk_frames (a count of frames,
        >= 1, default 8) is how many frames are processed at a time; both
        outputs are built chunk by chunk and do not depend on it. max_layers
        (a count of layers, an integer from 1 to 64, default 12) caps the
        number of blurred depth layers per frame.

        focus_x, focus_y (frame fractions, 0 left/top to 1 right/bottom; both
        negative = off, the default) focus each frame at the depth found at that
        point (see depth_at_point) instead of focus_m. rack_x, rack_y (same
        convention; needs the focus point) pull focus from the focus point to
        the rack point: frame i of N gets rack_focus_m(d_a, d_b, i / (N - 1),
        rack_start, rack_end) metres, with rack_start < rack_end fractions of
        the clip. bokeh_squeeze (unitless, 1.0 to 2.0, default 1.0) makes the
        bokeh that many times taller than wide, like an anamorphic lens.
        """
        t0 = time.perf_counter()
        common.check_chunk_frames(chunk_frames)
        if (isinstance(max_layers, bool) or not isinstance(max_layers, int)
                or not 1 <= max_layers <= 64):
            raise ValueError(f"max_layers must be an integer from 1 to 64, got {max_layers!r}")
        common.check_image(image)
        common.require_positive("focal_mm", focal_mm)
        common.require_positive("f_number", f_number)
        common.require_positive("focus_m", focus_m)
        common.require_positive("sensor_width_mm", sensor_width_mm)
        if not math.isfinite(max_radius_px) or max_radius_px < 0:
            raise ValueError(f"max_radius_px must be finite and >= 0, got {max_radius_px}")
        common.require_choice("quality", quality, list(_LAYERS))
        if not 1.0 <= bokeh_squeeze <= 2.0:
            raise ValueError(f"bokeh_squeeze must be from 1.0 to 2.0, got {bokeh_squeeze}")
        point = _point_on("focus", focus_x, focus_y)
        rack = _point_on("rack", rack_x, rack_y)
        if rack and not point:
            raise ValueError("a rack point needs a focus point (focus_x, focus_y)")
        if rack and not 0.0 <= rack_start < rack_end <= 1.0:
            raise ValueError(f"rack_start must be below rack_end, both from 0 to 1, got {rack_start}, {rack_end}")
        depth = common.resolve_depth(image, depth_mask, depth_image)
        if max_radius_px == 0:
            out = common.finish(image.clone())
            common.log_call("OpenOptics_DepthOfField", image, image.shape[0], chunk_frames,
                            time.perf_counter() - t0, layers=0)
            return (out, torch.zeros(image.shape[:3], dtype=torch.float32))
        focus_per_frame = None
        if point:
            focus_per_frame = depth_at_point(depth, focus_x, focus_y, focus_m)
            if rack:
                n = image.shape[0]
                ends = depth_at_point(depth, rack_x, rack_y, focus_m)
                focus_per_frame = [rack_focus_m(a, b, i / (n - 1) if n > 1 else 0.0, rack_start, rack_end)
                                   for i, (a, b) in enumerate(zip(focus_per_frame, ends))]
        device = get_device()
        stats = {}
        outs, cocs = [], []
        used_device = device
        for start, stop in common.chunk_ranges(image.shape[0], chunk_frames):
            linear = common.to_linear(image[start:stop].to(device), colorspace)
            depth_c = depth[start:stop].to(device)
            if focus_per_frame is None:
                radius = coc_radius_map(depth_c, focal_mm, f_number, focus_m, sensor_width_mm,
                                        max_radius_px)
                result = composite_layers(linear, depth_c, radius, _LAYERS[quality], focus_m,
                                          max_layers, stats, bokeh_squeeze=bokeh_squeeze)
            else:
                radii, results = [], []
                for j in range(stop - start):
                    f_m = focus_per_frame[start + j]
                    r = coc_radius_map(depth_c[j:j + 1], focal_mm, f_number, f_m, sensor_width_mm,
                                       max_radius_px)
                    results.append(composite_layers(linear[j:j + 1], depth_c[j:j + 1], r,
                                                    _LAYERS[quality], f_m, max_layers, stats,
                                                    bokeh_squeeze=bokeh_squeeze))
                    radii.append(r)
                radius, result = torch.cat(radii), torch.cat(results)
            used_device = result.device
            outs.append(common.finish(common.from_linear(result, colorspace)).cpu().to(torch.float32))
            cocs.append(common.finish(radius / float(max_radius_px)).cpu().to(torch.float32))
        common.log_call("OpenOptics_DepthOfField", used_device, image.shape[0], chunk_frames,
                        time.perf_counter() - t0, layers=stats.get('layers', 0))
        return (torch.cat(outs), torch.cat(cocs))
