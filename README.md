# Open Optics

Open Optics is a ComfyUI node pack of physically based lens effects. It covers depth of field from real lens and sensor maths, focal crop, lens distortion, vignette, chromatic aberration and anamorphic squeeze.

## Install

Clone or copy this folder into ComfyUI's custom nodes folder as `ComfyUI\custom_nodes\open-optics`. For example, run this inside `custom_nodes`:

```
git clone <repo-url> open-optics
```

No extra pip installs are needed, because torch and numpy come with ComfyUI. Then restart ComfyUI. The nodes appear under the category "Open Optics".

## Nodes

| Key | Display name | Description |
| --- | --- | --- |
| OpenOptics_Anamorphic | Open Optics: Anamorphic Squeeze | Takes an IMAGE, a squeeze factor, a mode (desqueeze or squeeze) and keep_width; returns an IMAGE. |
| OpenOptics_ChromaticAberration | Open Optics: Chromatic Aberration | Takes an IMAGE and red and blue lateral colour shifts (ca_r, ca_b); returns an IMAGE. |
| OpenOptics_DepthOfField | Open Optics: Depth of Field | Takes an IMAGE, focal length (mm), f-number, focus distance (m), sensor width (mm), quality, max radius, colorspace and an optional depth MASK or depth IMAGE; returns an IMAGE and a MASK of the circle of confusion in pixels (coc_px). |
| OpenOptics_DepthTemporalSmooth | Open Optics: Depth Temporal Smooth | Takes a depth MASK and a smoothing strength (0 to 1); returns a temporally smoothed depth MASK in metres (depth_m). |

## Example workflow

TODO

## Tests

TODO

## Licence

TODO
