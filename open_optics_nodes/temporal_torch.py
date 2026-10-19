"""Torch helpers for temporal depth smoothing (mirrors open_optics.temporal)."""

import torch

from open_optics.temporal import _require_strength
from open_optics_nodes.common import chunk_ranges


def _update_frame(est, pending, first_val, first_t, v, t, gain):
    """Advance the per-pixel smoothing state by one depth frame, in place.

    Args:
        est: float64 [H, W] running estimate in metres, nan where unset. Modified in place.
        pending: float64 [H, W] pending outlier depth in metres, nan for none. Modified in place.
        first_val: float64 [H, W] first valid depth in metres, nan for none. Modified in place.
        first_t: int64 [H, W] frame index of the first valid value, -1 for none. Modified in place.
        v: float64 [H, W] depth frame in metres.
        t: int frame index (unitless).
        gain: unitless blend gain, 1 - 0.9 * strength.

    Returns:
        The float64 [H, W] output for this frame in metres: the estimate, or v
        (as given) where the estimate is still unset.
    """
    valid = torch.isfinite(v) & (v > 0)
    unset = torch.isnan(est)
    has_pending = ~torch.isnan(pending)

    out_est = (v > 2.5 * est) | (v < 0.4 * est)
    out_pend = (v > 2.5 * pending) | (v < 0.4 * pending)

    init = valid & unset
    known = valid & ~unset
    blend = known & ~out_est
    accept = known & out_est & has_pending & ~out_pend
    spike = known & out_est & ~(has_pending & ~out_pend)

    new_est = torch.where(init | accept, v, est)
    new_est = torch.where(blend, est + gain * (v - est), new_est)
    new_pending = torch.where(blend | accept, torch.full_like(pending, float("nan")), pending)
    new_pending = torch.where(spike, v, new_pending)

    est.copy_(new_est)
    pending.copy_(new_pending)
    first_val.copy_(torch.where(init, v, first_val))
    first_t.copy_(torch.where(init, torch.full_like(first_t, t), first_t))
    return torch.where(torch.isnan(est), v, est)


def smooth_sequence_torch(depth, strength, chunk_frames, device):
    """Smooth a depth sequence over time, chunk by chunk, on a device.

    Args:
        depth: CPU tensor [B, H, W] of depths in metres.
        strength: unitless smoothing amount from 0 to 1; ValueError otherwise.
        chunk_frames: number of frames moved to the device at once.
        device: torch device to work on.

    Returns:
        (result, used_device): result is a CPU float32 [B, H, W] tensor of
        smoothed depths in metres (never-valid pixels are 1.0 m); used_device is
        the device of the working tensors, or device unchanged when nothing
        was computed (empty batch or strength 0).
    """
    strength = _require_strength(strength)
    ranges = chunk_ranges(depth.shape[0], chunk_frames)
    if strength == 0 or not ranges:
        return depth.to(torch.float32).clone(), device
    gain = 1 - 0.9 * strength
    shape = depth.shape[1:]
    est = torch.full(shape, float("nan"), dtype=torch.float64, device=device)
    pending = torch.full_like(est, float("nan"))
    first_val = torch.full_like(est, float("nan"))
    first_t = torch.full(shape, -1, dtype=torch.int64, device=device)
    used_device = est.device
    result = torch.empty(depth.shape, dtype=torch.float32)
    for start, stop in ranges:
        chunk = depth[start:stop].to(device=device, dtype=torch.float64)
        out = torch.stack(
            [_update_frame(est, pending, first_val, first_t, chunk[i], start + i, gain)
             for i in range(stop - start)]
        )
        result[start:stop] = out.to(device="cpu", dtype=torch.float32)
    first_val = first_val.to("cpu", torch.float32)
    first_t = first_t.cpu()
    frame_idx = torch.arange(depth.shape[0]).view(-1, 1, 1)
    result = torch.where(frame_idx < first_t, first_val.expand_as(result), result)
    result = torch.where(first_t == -1, torch.ones_like(result), result)
    return result, used_device
