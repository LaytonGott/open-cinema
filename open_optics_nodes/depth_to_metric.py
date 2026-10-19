"""Depth helpers for the Open Optics nodes (CPU torch tensors)."""

import math

import torch

from open_optics.depth import (metric_depth_coefficients, subject_median, subject_pixel,
                               validate_depth_params)
from open_optics_nodes import common
from open_optics_nodes.device import get_device


def depth_percentile_range(depth, low_percentile, high_percentile):
    """Return (d_lo, d_hi) percentile values of a whole depth batch.

    The whole tensor (all frames together) is flattened, non-finite values
    (NaN, +-inf) are dropped, and the rest is sorted. Percentiles are 0 to 100
    and depth values are unitless. Uses linear interpolation at position
    q/100*(n-1) over the n finite values, the same as torch.quantile. Returns
    two Python floats. Raises ValueError for an empty tensor, a tensor with no
    finite values, or a percentile outside 0 to 100.
    """
    flat = depth.detach().reshape(-1).to(torch.float64)
    if flat.numel() == 0:
        raise ValueError("depth must not be empty")
    flat = flat[torch.isfinite(flat)]
    n = flat.numel()
    if n == 0:
        raise ValueError("depth has no finite values")
    sorted_vals, _ = torch.sort(flat)

    def at(q):
        if not 0.0 <= q <= 100.0:
            raise ValueError(f"percentile must be 0 to 100, got {q}")
        pos = q / 100.0 * (n - 1)
        lo = math.floor(pos)
        hi = math.ceil(pos)
        frac = pos - lo
        a = float(sorted_vals[lo])
        b = float(sorted_vals[hi])
        return a + (b - a) * frac

    return at(low_percentile), at(high_percentile)


def depth_to_metric_tensor(depth, near_m, far_m, inverse_depth, low_percentile, high_percentile):
    """Convert a relative depth tensor of any shape to metres.

    near_m and far_m are distances in metres; percentiles are 0 to 100 and pick
    the depth values that map to the limits (see depth_percentile_range).
    Returns a float32 tensor of the same shape in metres, within [near_m, far_m].
    Non-finite depth entries are ignored in the fit and replaced before the
    mapping: NaN and -inf become d_lo, +inf becomes d_hi, so the result is
    always finite. Raises ValueError for bad near/far/percentiles or a depth
    with no finite values.
    """
    validate_depth_params(near_m, far_m, low_percentile, high_percentile)
    d_lo, d_hi = depth_percentile_range(depth, low_percentile, high_percentile)
    return _map_to_metric(depth, d_lo, d_hi, near_m, far_m, inverse_depth)


def _map_to_metric(depth, d_lo, d_hi, near_m, far_m, inverse_depth):
    """Map a depth tensor to metres with an already fitted (d_lo, d_hi).

    near_m and far_m are in metres; d_lo and d_hi are unitless depth values.
    Returns a float32 tensor of the same shape and device in metres.
    """
    a, b, reciprocal = metric_depth_coefficients(d_lo, d_hi, near_m, far_m, inverse_depth)
    d = depth.detach().to(torch.float64)
    d = torch.where(torch.isposinf(d), torch.full_like(d, d_hi), d)
    d = torch.where(torch.isfinite(d), d, torch.full_like(d, d_lo))
    v = a * d + b
    if reciprocal:
        z = 1.0 / torch.clamp(v, 1.0 / far_m, 1.0 / near_m)
    else:
        z = torch.clamp(v, near_m, far_m)
    return z.to(torch.float32)


def _validate_subject_params(mode, subject_m, near_m, far_m, subject_x, subject_y,
                             subject_radius_px):
    """Validate the DepthToMetric mode and subject inputs.

    subject_m, near_m and far_m are in metres; subject_x and subject_y are
    0 to 1 fractions of the image width and height; subject_radius_px is in
    pixels. Returns None. Raises ValueError for a mode other than 'near_far'
    or 'subject', subject_m <= 0, subject_m outside [near_m, far_m],
    subject_x or subject_y outside 0 to 1, or subject_radius_px < 0.
    """
    if mode not in ("near_far", "subject"):
        raise ValueError(f"unknown mode {mode!r}, expected 'near_far' or 'subject'")
    if not subject_m > 0:
        raise ValueError(f"subject_m must be > 0 m, got {subject_m}")
    if not near_m <= subject_m <= far_m:
        raise ValueError(
            f"subject_m must be within [near_m, far_m] = [{near_m}, {far_m}] m, got {subject_m}")
    if not 0.0 <= subject_x <= 1.0:
        raise ValueError(f"subject_x must be 0 to 1, got {subject_x}")
    if not 0.0 <= subject_y <= 1.0:
        raise ValueError(f"subject_y must be 0 to 1, got {subject_y}")
    if subject_radius_px < 0:
        raise ValueError(f"subject_radius_px must be >= 0 px, got {subject_radius_px}")


def _subject_region_values(depth, col, row, radius):
    """Return the depth values in a square window around the subject pixel.

    depth is a tensor [B, H, W] of unitless depth values; col and row are the
    0-based integer subject pixel; radius is a pixel count >= 0. The window
    covers rows row-radius..row+radius and columns col-radius..col+radius,
    clipped to the image, taken from all B frames together (frame-major order).
    Returns a 1-D float64 tensor of the window values (unitless).
    """
    h, w = depth.shape[1], depth.shape[2]
    r0, r1 = max(row - radius, 0), min(row + radius + 1, h)
    c0, c1 = max(col - radius, 0), min(col + radius + 1, w)
    return depth.detach()[:, r0:r1, c0:c1].reshape(-1).to(torch.float64)


def _subject_mask_region(subject_mask, depth_shape):
    """Return the subject region of a mask as a bool tensor [B, H, W].

    subject_mask is a unitless tensor [B, H, W] or [1, H, W]; depth_shape is
    (B, H, W) in pixels. A [1, H, W] mask is expanded to all B frames. Raises
    ValueError if the mask shape does not match or no pixel is above 0.5.
    Returns a bool tensor [B, H, W], True where subject_mask > 0.5.
    """
    b, h, w = depth_shape
    shape = tuple(subject_mask.shape)
    if len(shape) != 3 or shape[1:] != (h, w) or shape[0] not in (b, 1):
        raise ValueError(
            f"subject_mask has shape {shape}, expected ({b}, {h}, {w}) "
            f"or (1, {h}, {w})")
    region = (subject_mask > 0.5).expand(b, h, w)
    if not bool(region.any()):
        raise ValueError("subject_mask is empty: no pixel above 0.5")
    return region


def _subject_frame_depths(depth, region):
    """Return the per-frame subject depth as a float64 tensor [B].

    depth is a float tensor [B, H, W] (unitless depth values); region is a
    bool tensor [B, H, W] marking the subject pixels. Each element is the
    median of depth[b][region[b]] from subject_median (unitless; the mean of
    the two middle values for an even count). Raises ValueError, naming the
    frame index, if a frame has no True pixel in region.
    """
    out = []
    for b in range(depth.shape[0]):
        values = depth[b][region[b]].detach().to(torch.float64)
        if values.numel() == 0:
            raise ValueError(f"frame {b} has no subject pixel in region")
        out.append(subject_median(values.tolist()))
    return torch.tensor(out, dtype=torch.float64)


def _subject_to_metric(depth, d_s, subject_m, near_m, far_m, inverse_depth):
    """Map a depth tensor to metres by scale from the subject depth.

    depth is a tensor of any shape with unitless values; d_s is the unitless
    subject depth (> 0), either a Python float (one scale for all of depth) or
    a tensor of shape [n,1,1] (one value per frame, broadcast over depth
    [n,H,W]; it is moved to depth's device and cast to float64). subject_m,
    near_m and far_m are in metres. Torch form
    of open_optics.depth.subject_scale_metric: subject_m*d_s/d if
    inverse_depth else subject_m*d/d_s, where inverse_depth entries with
    d <= 0 become far_m. Returns a float32 tensor of the same shape and device
    in metres, clamped to [near_m, far_m].
    """
    d = depth.detach().to(torch.float64)
    if torch.is_tensor(d_s):
        d_s = d_s.detach().to(device=d.device, dtype=torch.float64)
    if inverse_depth:
        positive = d > 0
        safe = torch.where(positive, d, torch.ones_like(d))
        z = torch.where(positive, subject_m * d_s / safe, torch.full_like(d, far_m))
    else:
        z = subject_m * d / d_s
    return torch.clamp(z, near_m, far_m).to(torch.float32)


class OpenOptics_DepthToMetric:
    """Convert a relative depth map to metric depth in metres."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "near_m": ("FLOAT", {"default": 0.5, "min": 0.001, "max": 100000.0, "step": 0.1}),
                "far_m": ("FLOAT", {"default": 10.0, "min": 0.001, "max": 100000.0, "step": 0.1}),
                "inverse_depth": ("BOOLEAN", {"default": True}),
                "low_percentile": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "high_percentile": ("FLOAT", {"default": 98.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "chunk_frames": common.CHUNK_FRAMES_INPUT,
                "mode": (["near_far", "subject"], {"default": "near_far"}),
                "subject_m": ("FLOAT", {"default": 3.0, "min": 0.001, "max": 100000.0, "step": 0.1}),
                "subject_x": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "subject_y": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "subject_radius_px": ("INT", {"default": 4, "min": 0, "max": 10000}),
                "anchor_scope": (["batch", "frame"], {"default": "batch"}),
            },
            "optional": {
                "depth_mask": ("MASK",),
                "depth_image": ("IMAGE",),
                "subject_mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("MASK", "IMAGE")
    RETURN_NAMES = ("depth_m", "preview")
    FUNCTION = "convert"
    CATEGORY = "Open Optics"

    def convert(self, near_m=0.5, far_m=10.0, inverse_depth=True, low_percentile=2.0,
                high_percentile=98.0, depth_mask=None, depth_image=None, chunk_frames=8,
                mode="near_far", subject_m=3.0, subject_x=0.5, subject_y=0.5,
                subject_radius_px=4, anchor_scope="batch", subject_mask=None):
        """Convert relative depth to metres.

        mode ("near_far" or "subject"), subject_m (metres), subject_x and
        subject_y (0 to 1 image position) and subject_radius_px (pixels) are
        the subject inputs. In subject mode the median depth in the window
        around the subject point (all frames) sets the scale so that it maps
        to subject_m, and the percentiles are ignored.
        subject_mask: MASK [B,H,W] or [1,H,W], pixels above 0.5 are the
        subject; in subject mode the median depth over those pixels (all
        frames) replaces the point window, so subject_x, subject_y and
        subject_radius_px are not used for the region when it is connected.
        Raises ValueError if its shape does not match or it is empty.
        anchor_scope: 'batch' or 'frame' (not used yet).

        near_m and far_m are in metres; percentiles are 0 to 100. Exactly one
        of depth_mask or depth_image must be connected. The percentile fit uses
        the whole batch once; chunk_frames (a count of frames, >= 1, default 8)
        is how many frames are then converted at a time on get_device(), and
        the result does not depend on it. Returns a 2-tuple of CPU tensors:
        depth_m, a float32 MASK [B, H, W] in metres, and preview, a float32
        IMAGE [B, H, W, 3] with (far_m - Z) / (far_m - near_m) clamped to 0..1.
        Raises ValueError for bad inputs.
        """
        if mode == "subject":
            _validate_subject_params(mode, subject_m, near_m, far_m, subject_x,
                                     subject_y, subject_radius_px)
            if anchor_scope not in ("batch", "frame"):
                raise ValueError(
                    f"unknown anchor_scope {anchor_scope!r}, expected 'batch' or 'frame'")
        elif mode != "near_far":
            raise ValueError(f"unknown mode {mode!r}, expected 'near_far' or 'subject'")
        common.check_chunk_frames(chunk_frames)
        depth = common.resolve_depth(None, depth_mask, depth_image)
        if mode == "subject":
            if subject_mask is not None:
                region = _subject_mask_region(subject_mask, tuple(depth.shape))
                values = depth.detach()[region].to(torch.float64)
            else:
                col, row = subject_pixel(subject_x, subject_y, depth.shape[2], depth.shape[1])
                values = _subject_region_values(depth, col, row, subject_radius_px)
            d_s = subject_median(values.tolist())
            if not math.isfinite(d_s) or not d_s > 0:
                raise ValueError(f"subject depth must be finite and > 0, got {d_s}")
        else:
            validate_depth_params(near_m, far_m, low_percentile, high_percentile)
            d_lo, d_hi = depth_percentile_range(depth, low_percentile, high_percentile)
        device = get_device()
        zs = []
        previews = []
        for start, stop in common.chunk_ranges(depth.shape[0], chunk_frames):
            chunk = depth[start:stop].to(device)
            if mode == "subject":
                z = _subject_to_metric(chunk, d_s, subject_m, near_m, far_m, inverse_depth)
            else:
                z = _map_to_metric(chunk, d_lo, d_hi, near_m, far_m, inverse_depth)
            shade = torch.clamp((far_m - z) / (far_m - near_m), 0.0, 1.0)
            preview = shade.unsqueeze(-1).repeat(1, 1, 1, 3)
            zs.append(z.cpu().to(torch.float32))
            previews.append(preview.cpu().to(torch.float32))
        return (torch.cat(zs), torch.cat(previews))
