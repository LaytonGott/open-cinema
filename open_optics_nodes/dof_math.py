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
    focus_mm = focus_m * 1000.0
    # A scalar call validates the arguments (raises ValueError) and gives the scale.
    scale = coc.blur_diameter_mm(focal_mm, f_number, focus_mm, math.inf)
    coc.blur_radius_px(scale, width, sensor_width_mm, max_px=max_radius_px)
    subject_mm = depth * 1000.0
    blur_mm = scale * (subject_mm - focus_mm) / subject_mm
    radius = blur_mm.abs() * width / sensor_width_mm / 2
    return radius.clamp(max=max_radius_px).to(torch.float32)


SHARP_RADIUS_PX = 0.5


def _radius_level(radius):
    """Return log(radius / SHARP_RADIUS_PX) for a blur radius map in pixels.

    radius is a float32 tensor in pixels, clamped below at SHARP_RADIUS_PX, so
    the result is >= 0 (unitless). Equal steps in level are equal ratios of
    radius, which is how layers are binned.
    """
    return torch.log(radius.clamp_min(SHARP_RADIUS_PX) / SHARP_RADIUS_PX)


FOCUS_REACH_PX = 6
FOCUS_COLOUR_TOL = 0.05


def grow_focus_into_far(signed_radius, image_chw, focus_reach_px=FOCUS_REACH_PX,
                        colour_tol=FOCUS_COLOUR_TOL):
    """Pull the subject's own soft-depth edge pixels into focus; returns the signed radius.

    signed_radius is a float32 [B, H, W] CoC radius in pixels, negative in
    front of focus and positive behind; image_chw is the float32 [B, 3, H, W]
    linear image. Monocular depth (DA3) is soft over 2-4 px at a subject's
    silhouette, so the subject's edge pixels get a background CoC. Blurred as
    background they spread the subject's colour into it, which drew a dark
    line in thin gaps such as between an arm and the body.

    Depth cannot tell those pixels apart: with a 4 px soft edge, the subject
    pixels beside a 2 px gap have exactly the gap's depth, so any growth by
    depth or edge width alone either misses them or also freezes the gap and
    a ring of background around the subject (a fixed 2 px growth did the
    first on the street clip). Colour can: the in-focus region grows one pixel
    at a time, up to focus_reach_px pixels, into behind-focus pixels that
      - touch the region (8-neighbourhood),
      - have a colour within colour_tol (linear, Euclidean over RGB) plus two
        local standard deviations of the mean colour of the in-focus pixels
        within focus_reach_px, i.e. look like the subject there, and
      - have a CoC radius of at least the step number in pixels, i.e. sit on a
        depth edge where blur rises by >= 1 px per pixel, not on a gently
        receding surface such as a floor, which keeps its blur.
    Grown pixels get radius 0. Background next to the subject differs in
    colour and keeps its blur, so no sharp background ring forms; the cost is
    that background of the subject's colour within the reach, at a depth
    edge, is kept sharp too, and subject edge pixels whose colour is far from
    the local subject colour (anti-aliased edge pixels, strong texture) are
    still blurred as background. Near-side pixels are left alone, so a
    blurred foreground still spreads over the subject. Returns a float32
    [B, H, W] signed radius in pixels; focus_reach_px 0 returns signed_radius
    unchanged.
    """
    in_focus = signed_radius.abs() < SHARP_RADIUS_PX
    if focus_reach_px <= 0 or not in_focus.any():
        return signed_radius
    reach = int(focus_reach_px)
    region = in_focus.to(torch.float32)[:, None]
    image = image_chw.to(torch.float32)

    def local_mean(x):
        return torch.nn.functional.avg_pool2d(x, 2 * reach + 1, stride=1, padding=reach,
                                              count_include_pad=False)

    share = local_mean(region)
    mean = local_mean(image * region) / share.clamp_min(1e-8)
    var = (local_mean(image * image * region) / share.clamp_min(1e-8) - mean * mean)
    var = var.clamp_min(0.0).sum(dim=1, keepdim=True)
    dist2 = ((image - mean) ** 2).sum(dim=1, keepdim=True)
    candidate = ((share > 0) & (dist2 <= colour_tol ** 2 + 4.0 * var)
                 & (signed_radius > 0)[:, None])
    radius = signed_radius.abs()[:, None]
    for step in range(1, reach + 1):
        touching = torch.nn.functional.max_pool2d(region, 3, stride=1, padding=1) > 0
        add = touching & (region == 0) & candidate & (radius >= step)
        if not add.any():
            break
        region = region + add.to(torch.float32)
    grown = (region[:, 0] > 0) & ~in_focus
    return torch.where(grown, torch.zeros_like(signed_radius), signed_radius)


def _side_layers(level, side, width):
    """Split one side (near or far) of the frame into masks by blur radius.

    level is _radius_level of the float32 [B, H, W] blur radius in pixels and
    side a bool mask of the pixels on this side, all with radius >=
    SHARP_RADIUS_PX. The side's level range [0, max] is split into equal bins
    about width wide (at least one), so every bin spans the same ratio of
    radii. Returns the non-empty bin masks, smallest radius first.
    """
    if not side.any():
        return []
    extent = level[side].max().item()
    if extent <= 0.0 or width <= 0.0:
        return [side]
    count = max(1, math.ceil(extent / width - 1e-6))
    idx = (level / extent * count).floor().long().clamp(0, count - 1)
    masks = [side & (idx == b) for b in range(count)]
    return [m for m in masks if m.any()]


def composite_layers(image_linear, depth_m, radius_map, n_layers, focus_m,
                     max_layers=None, stats=None, focus_reach_px=FOCUS_REACH_PX):
    """Blur signed CoC layers and composite them back to front; returns float32 [B, H, W, 3].

    Layers are chosen per frame, so the result does not depend on how frames
    are batched. See _composite_frames for the layer rules; arguments are as
    there: image_linear float32 [B, H, W, 3], depth_m (metres) and radius_map
    (pixels) float32 [B, H, W], focus_m in metres, max_layers an optional cap
    on blurred layers per frame (None for no cap), stats an optional dict
    that receives the largest layer count used as stats['layers'], and
    focus_reach_px (pixels, default FOCUS_REACH_PX) how far the in-focus
    region may grow into the subject's soft-depth edge before layering (see
    grow_focus_into_far; 0 turns it off).
    """
    frames = [
        _composite_frames(image_linear[i:i + 1], depth_m[i:i + 1], radius_map[i:i + 1],
                          n_layers, focus_m, max_layers, stats, focus_reach_px)
        for i in range(image_linear.shape[0])
    ]
    return torch.cat(frames, dim=0)


def _composite_frames(image_linear, depth_m, radius_map, n_layers, focus_m,
                      max_layers=None, stats=None, focus_reach_px=FOCUS_REACH_PX):
    """Composite one batch with bins from the whole batch; returns float32 [B, H, W, 3].

    image_linear is float32 [B, H, W, 3] in linear light; depth_m (metres) and
    radius_map (pixels) are float32 [B, H, W]; focus_m is the focus distance in
    metres. The CoC is signed, negative in front of focus_m, and behind-focus
    pixels at the subject's soft depth edge that look like the subject, up to
    focus_reach_px pixels out, are first made in focus (grow_focus_into_far),
    so they are not blurred into the background as the subject's colour.
    Pixels with a radius below 0.5 px form one in-focus layer that is
    never blurred. The rest are split by sign, far (behind focus_m) or near,
    and quantised by radius: the near and far radius ranges share n_layers bins
    of equal ratio (equal width in log radius), each non-empty side getting at
    least one, and empty bins are skipped. Equal ratios keep a layer's radius
    close to each member's own: with equal widths in pixels, a sub-pixel CoC
    at a subject's edge shared a layer with soft background a few pixels
    wide, and the background bled into the subject, leaving a dark outline.
    Each layer's premultiplied colour and alpha are
    blurred with its mean radius in pixels, then composited with "over" from
    back to front: far layers from largest radius to smallest, the in-focus
    layer, then near layers from smallest radius to largest. The result is
    clamped to 0..1. If max_layers is given, at most that many layers are
    blurred (the in-focus layer counts as one): the log-radius bin width is
    multiplied by 1.5 until the non-sharp layers fit max_layers - 1; if even
    one layer per side is too many, all non-sharp pixels form one layer, and
    max_layers == 1 puts every pixel in one layer blurred with the mean radius
    (pixels) of radius_map. If stats is a dict, stats['layers'] becomes the
    larger of its value and the number of layers used here.
    """
    image = image_linear.to(torch.float32)
    depth = sanitize_depth(depth_m)
    radius = radius_map.to(torch.float32)
    chw = image.permute(0, 3, 1, 2)
    signed = grow_focus_into_far(torch.where(depth >= focus_m, radius, -radius),
                                 chw, focus_reach_px)
    radius = signed.abs()
    sharp = radius < SHARP_RADIUS_PX
    far = ~sharp & (signed > 0)
    near = ~sharp & ~far
    level = _radius_level(radius)
    extents = [level[s].max().item() for s in (near, far) if s.any()]
    width = sum(extents) / max(n_layers, 1)

    def build(w):
        return (list(reversed(_side_layers(level, far, w))) + [sharp]
                + _side_layers(level, near, w))

    layers = build(width)
    if max_layers is not None:
        budget = max(max_layers - 1, 0)
        if max_layers <= 1:
            layers = [torch.ones_like(sharp)]
        else:
            while width > 0.0 and len(layers) - 1 > budget and width < 1e6:
                width *= 1.5
                layers = build(width)
            if len(layers) - 1 > budget:
                layers = [~sharp, sharp]
    out = torch.zeros_like(chw)
    cov = torch.zeros_like(chw[:, :1])
    used = 0
    for mask in layers:
        if not mask.any():
            continue
        used += 1
        alpha = mask.to(torch.float32)[:, None]
        layer_radius = 0.0 if mask is sharp else radius[mask].mean().item()
        res = blur_layer(torch.cat([chw * alpha, alpha], dim=1), layer_radius)
        colour_b = res[:, :3]
        alpha_b = res[:, 3:]
        out = colour_b + out * (1.0 - alpha_b)
        cov = alpha_b + cov * (1.0 - alpha_b)
    if stats is not None:
        stats['layers'] = max(stats.get('layers', 0), used)
    out = out / cov.clamp_min(1e-8)
    return out.permute(0, 2, 3, 1).clamp(0.0, 1.0).contiguous()
