"""Torch helpers for temporal depth smoothing (mirrors open_optics.temporal)."""

import torch


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
