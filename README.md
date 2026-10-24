# Open Optics

Open Optics is a ComfyUI node pack of physically based lens effects. It covers depth of field from real lens and sensor maths, focal crop, lens distortion, vignette, chromatic aberration and anamorphic squeeze.

## Install

Clone or copy this folder into ComfyUI's custom nodes folder as `ComfyUI\custom_nodes\open-optics`. For example, run this inside `custom_nodes`:

```
git clone <repo-url> open-optics
```

No extra pip installs are needed, because torch and numpy come with ComfyUI. Then restart ComfyUI. The nodes appear under the category "Open Optics".

### Device

The nodes run on ComfyUI's device when it has a GPU and fall back to the CPU otherwise. Set the environment variable `OPEN_OPTICS_DEVICE` to `cpu`, `cuda` or `auto` to override this. For long videos, set the `chunk_frames` input to limit memory use.

## Nodes

| Key | Display name | Description |
| --- | --- | --- |
| OpenOptics_Anamorphic | Open Optics: Anamorphic Squeeze | Takes an IMAGE, a squeeze factor, a mode (desqueeze or squeeze) and keep_width; returns an IMAGE. |
| OpenOptics_ChromaticAberration | Open Optics: Chromatic Aberration | Takes an IMAGE and red and blue lateral colour shifts (ca_r, ca_b); returns an IMAGE. |
| OpenOptics_DepthOfField | Open Optics: Depth of Field | Takes an IMAGE, focal length (mm), f-number, focus distance (m), sensor width (mm), quality, max radius, colorspace and an optional depth MASK or depth IMAGE; returns an IMAGE and a MASK of the circle of confusion in pixels (coc_px). |
| OpenOptics_DepthTemporalSmooth | Open Optics: Depth Temporal Smooth | Takes a depth MASK and a smoothing strength (0 to 1); returns a temporally smoothed depth MASK in metres (depth_m). |
| OpenOptics_DepthToMetric | Open Optics: Depth to Metric | Takes an optional depth MASK or depth IMAGE, near and far distances (m), inverse_depth, percentiles, a mode (near_far or subject) with subject point, radius and optional subject MASK, and anchor_scope; returns a metric depth MASK in metres (depth_m) and a preview IMAGE. |
| OpenOptics_FocalCrop | Open Optics: Focal Crop | Takes an IMAGE, source and target focal lengths (mm) and an output_size (original or cropped); returns an IMAGE. |
| OpenOptics_LensDistortion | Open Optics: Lens Distortion | Takes an IMAGE, focal length (mm), sensor width (mm), radial k1 to k3 and tangential p1, p2 coefficients, a direction (apply or remove) and fit (keep or crop); returns an IMAGE. |
| OpenOptics_Vignette | Open Optics: Vignette | Takes an IMAGE, focal length (mm), sensor width (mm), strength (0 to 1) and colorspace; returns an IMAGE. |

## Example workflow

In ComfyUI, load `workflows/open_optics_demo.json` (menu Workflow > Open, or drag the file onto the canvas).

Place two images in ComfyUI's input folder (`ComfyUI\input`): a photo, and a depth map such as Depth Anything produces (white = near, or grey-scale depth). Then set each of the two LoadImage nodes to the right file: the photo node feeds the chain, and the depth-map node feeds Depth to Metric.

The stages, in order:

1. Open Optics: Depth to Metric converts the depth map to metres.
2. Open Optics: Focal Crop crops the photo to the field of view of a different focal length.
3. Open Optics: Depth of Field blurs by distance, using the metric depth as `depth_mask`.
4. Open Optics: Lens Distortion applies barrel or pincushion distortion.
5. Open Optics: Vignette darkens the corners.
6. Open Optics: Chromatic Aberration shifts the red and blue channels.
7. Open Optics: Anamorphic Squeeze squeezes or desqueezes the width.
8. Preview Image shows the result.

Queue/Run produces a preview image.

## Helpers

`open_optics/framing.py` has three plain Python helpers for framing estimates: `sensor_height_mm` (sensor height from sensor width and image size), `subject_distance_m` (how far away a subject of known height is) and `subject_height_px` (the inverse: how tall a subject appears at a given distance).

Worked example: a 1.7 m person fills half the frame (600 of 1200 px) with a 50 mm lens on a 24 mm tall sensor. The subject's height on the sensor is h = 24 * 600 / 1200 = 12 mm, and with u = f * (1 + H / h) the distance is 50 * (1 + 1700 / 12) mm, about 7.1 m.

```python
from open_optics.framing import subject_distance_m
subject_distance_m(focal_mm=50, sensor_height_mm=24, subject_height_px=600, image_height_px=1200)
# about 7.13 m (50 * (1 + 1700/12) / 1000 = 7.1333)
```

This is an estimate: it assumes a thin lens and a subject facing the camera. There is no ComfyUI node for these helpers.

## Run the director app

1. You need ComfyUI portable v0.41 or newer with the Open Cinema pack in `ComfyUI\custom_nodes` as in the Install section, the ComfyUI-GGUF custom node, and a Depth Anything 3 custom node that provides `LoadDA3Model`, `DA3Inference` and `DA3Render` (the one installed in this project's ComfyUI). You also need these model files: `ltx-2-19b-distilled_Q4_K_M.gguf` in `models\diffusion_models`, `gemma_3_12B_it_fp8_scaled.safetensors` in `models\text_encoders`, `ltx-2-19b-embeddings_connector_distill_bf16.safetensors` and `LTX2_audio_vae_bf16.safetensors` in `models\checkpoints`, `LTX2_video_vae_bf16.safetensors` in `models\vae`, `ltx-2-spatial-upscaler-x2-1.0.safetensors` in `models\latent_upscale_models`, and `depth_anything_3_mono_large.safetensors` in `models\geometry_estimation`. `docs/benchmarks.md` has the sources.
2. Install the app's packages into the project's venv: `pip install -r app/requirements.txt`. On Windows: `.venv\Scripts\pip install -r app/requirements.txt`.
3. Start ComfyUI with `run_nvidia_gpu.bat` in the portable folder and wait for the line `To see the GUI go to`.

## Tests

Run all tests with `npm test`. Run the GPU benchmarks with `npm run test:bench` (it sets `OPEN_OPTICS_BENCH=1`).

The project uses a dedicated Python virtual environment (`.venv`) with CUDA-enabled torch. Set `OPEN_OPTICS_PYTHON` to use a different Python.

Tests run on the CPU or the GPU, chosen with `OPEN_OPTICS_DEVICE` (`cpu`, `cuda` or `auto`).

## Licence

The pack is released under GPL-3.0 (see LICENSE).

What was checked: a scan of the root `__init__.py`, `open_optics/` and `open_optics_nodes/` for ComfyUI imports found one, the guarded, optional `import comfy.model_management` in `open_optics_nodes/device.py` (the scan is recorded in `docs/licence-scan.md` and checked by `tests/test_release.py`). ComfyUI's own LICENSE is GPL-3.0. Because the pack imports ComfyUI code, it is used as a combined work with ComfyUI, so GPL-3.0 applies. If no such import existed, MIT would have been chosen.

The hardware-selection helper `get_device()` in `open_optics_nodes/device.py` optionally uses ComfyUI's model management (`import comfy.model_management`, guarded, only when ComfyUI is loaded). This is the only ComfyUI code the pack uses.

Copied code: no code was copied from other node packs, in particular none from the packs that `docs/research.md` lists as having no LICENSE file (for example ComfyUI-Darkroom). The lens maths is original and written from published formulas. Dependencies: torch and numpy are provided by ComfyUI and are not bundled with this pack.
