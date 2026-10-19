# Depth to Metric: subject mode

`OpenOptics_DepthToMetric` converts a relative depth map to metres. It has two
modes, chosen with the `mode` input.

- `near_far` (the default, unchanged): the depth range, trimmed by
  `low_percentile` and `high_percentile`, is mapped onto `near_m` to `far_m`.
- `subject`: the depth is scaled so that a chosen subject lands at a distance
  you give in metres.

## Inputs added for subject mode

| Input | Type, unit | Default | Meaning |
|---|---|---|---|
| `mode` | `near_far` or `subject` | `near_far` | Choice of mapping. |
| `subject_m` | float, metres | 3.0 | Distance the subject maps to. Must be > 0 and within `near_m` to `far_m`. |
| `subject_x` | float, 0..1 fraction of image width | 0.5 | Subject point, column = `round(x*(W-1))`. |
| `subject_y` | float, 0..1 fraction of image height | 0.5 | Subject point, row = `round(y*(H-1))`. |
| `subject_radius_px` | int, pixels | 4 | Half-size of the square window around the point (0 = one pixel). The window is clipped to the image. |
| `anchor_scope` | `batch` or `frame` | `batch` | `batch` pools all frames into one scale; `frame` gives each frame its own scale. |
| `subject_mask` | optional MASK `[B,H,W]` or `[1,H,W]` | none | Pixels with value > 0.5 are the subject. When connected it overrides the point (`subject_x`, `subject_y`, `subject_radius_px` are not used). |

## Anchor depth d_s

The anchor `d_s` is the median of the depth values in the subject region (the
window or the mask). For an even count it is the mean of the two middle values.
With `anchor_scope = batch` the values of all frames are pooled and one `d_s`
is used for the whole batch; with `frame` each frame's region gives its own
`d_s`, so the subject of every frame maps to `subject_m`.

## Scale-only mapping

There is no offset, only a scale:

- `inverse_depth` on: `Z = subject_m * d_s / d`
- `inverse_depth` off: `Z = subject_m * d / d_s`

Where `d` is the input depth. With `inverse_depth` on, entries with `d <= 0`
map to `far_m`. The result is then clamped to `[near_m, far_m]`. In subject
mode `low_percentile` and `high_percentile` are ignored.

## Validation errors

A `ValueError` is raised for: a `mode` other than `near_far` or `subject`;
`subject_m <= 0` or outside `[near_m, far_m]`; `subject_x` or `subject_y`
outside 0 to 1; `subject_radius_px < 0`; an `anchor_scope` other than `batch`
or `frame`; a `subject_mask` whose shape does not match the depth, or with no
pixel above 0.5 (in `frame` scope, in any frame); a frame with no subject
pixel in the region; and a depth value or median `d_s` in the region that is
not finite and > 0.

## Feeding Depth of Field

The output is a metric depth map in metres, so it connects to the Depth of
Field node. Set that node's `focus_m` equal to `subject_m` and the subject is
sharp (circle of confusion 0), with everything else blurred by its distance
from that plane.

## Worked example

A 9x9 depth map, `inverse_depth` off, `near_m = 1.0`, `far_m = 10.0`,
`subject_m = 2.0`, `subject_x = subject_y = 0.5`, `subject_radius_px = 1`.
The point is pixel `round(0.5*8), round(0.5*8)` = (4, 4), so the window is the
3x3 block at rows and columns 3 to 5.

- Window pixels have depth 1.0, so the median `d_s` = 1.0.
- Those pixels map to `Z = 2.0 * 1.0 / 1.0` = **2.0 m**.
- Other pixels have depth 2.0 and map to `Z = 2.0 * 2.0 / 1.0` = **4.0 m**.
- A pixel of depth 0.25 would give 0.5 m and a pixel of depth 10.0 would give
  20 m; after the clamp they are 1.0 m and 10.0 m.
