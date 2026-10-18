# Open Optics: node pack spec (draft v0.1)

Open Optics is a ComfyUI custom-node pack. It turns a generated image or video into what a real camera and lens would have recorded.

You pick a **camera body**, a **lens**, an **aperture** and a **focus distance** once. That one choice then drives:
- the **prompt**,
- the **camera move**,
- and **physically computed** depth of field, distortion, chromatic aberration, vignetting, anamorphic effects and focus breathing.

No existing pack does this. See [research.md §4](research.md#4-has-anyone-published-a-lensoptics-node-pack).

Status: draft spec, no code yet. Open questions are listed at the end.

---

## 1. Conventions (apply to every node)

| Topic | Rule |
|---|---|
| Units | All lengths in **millimetres**. This includes focal length, sensor size, focus and subject distance, and circle of confusion (CoC). Angles are in degrees at the node UI and radians internally. |
| Image tensors | ComfyUI `IMAGE` is `[B, H, W, C]` float32 in 0–1. Video is a batch of frames (B = frame count). |
| Colour space | Every optical operation runs in **linear light**. Inputs are assumed sRGB-encoded; each image node has a `colorspace` input (`srgb` default, or `linear`). |
| sRGB decode | `L = C/12.92` if `C ≤ 0.04045`, else `((C+0.055)/1.055)^2.4` |
| sRGB encode | `C = 12.92·L` if `L ≤ 0.0031308`, else `1.055·L^(1/2.4) − 0.055` |
| Pixel coordinates | The origin is the top-left pixel centre. The principal point defaults to the image centre `(c_x, c_y) = ((W−1)/2, (H−1)/2)`. |
| Pixel pitch | `p = sensor_w / W` mm per pixel, using the **active** sensor width. Square pixels after desqueeze. |
| Focal length in pixels | `f_px = f / p = f · W / sensor_w` |
| Device | Runs on CUDA when available, with a CPU fallback. Every op is pure PyTorch; no custom CUDA kernels in v1. |
| Determinism | Fixed seeds wherever randomness is used. With identical inputs, output is bit-identical on the same device. |

### Custom data types
These are passed between nodes as plain Python dataclasses, serialisable to JSON so they can live in workflow files.

```
OO_CAMERA  { name, sensor_w_mm, sensor_h_mm, coc_mm (optional override) }
OO_LENS    { name, focal_mm, f_min (widest), f_max, t_loss_stops,
             squeeze (1.0 spherical | 1.33 | 1.5 | 1.8 | 2.0),
             k1, k2, k3, p1, p2,                 # Brown-Conrady distortion
             ca_r, ca_b,                         # lateral CA, radial scale offsets
             vig_mech, vig_stop_out,             # mechanical vignetting
             blades, blade_rotation_deg, blade_curvature,
             cats_eye, breathing, close_focus_mm,
             flare_tint_rgb, flare_strength }
OO_SHOT    { camera: OO_CAMERA, lens: OO_LENS, f_number, focus_mm,
             focus_curve: list[float] | None }   # per-frame focus for video
```

---

## 2. Nodes

The pack has 14 nodes in three groups:
- **Setup:** 1–3
- **Calculators:** 4–5 (no image work)
- **Image/video ops:** 6–13, plus the integration node 14

### 2.1 `OpenOptics.CameraBody` (Setup)
Defines the sensor or film gate.

| Input | Type | Default | Notes |
|---|---|---|---|
| preset | combo | `Full Frame 36×24` | Generic gate names; see below |
| sensor_w_mm, sensor_h_mm | float | from preset | Used when preset = `Custom` |
| coc_mm | float | 0 = auto | Overrides the CoC formula (§2.5) |

**Output:** `OO_CAMERA`

Presets ship as data in `presets/cameras.json`. The values are gate dimensions and must be checked against manufacturer data sheets before release (see Test C1).

| Preset | w × h (mm) |
|---|---|
| Super 16 | 12.52 × 7.41 |
| Super 35 (ANSI 3-perf area) | 24.89 × 18.66 |
| Large-format "S35 open gate" (ALEXA 35-class) | 27.99 × 19.22 |
| Full Frame | 36.00 × 24.00 |
| Large Format (Mini LF-class, open gate) | 36.70 × 25.54 |
| VistaVision 8K (V-Raptor-class) | 40.96 × 21.60 |
| 65 mm (5-perf) | 52.48 × 23.01 |

Preset names describe sensor formats and do not use brand names as product claims. This follows the competition's no-unlicensed-IP rule.

### 2.2 `OpenOptics.Lens` (Setup)

| Input | Type | Default | Notes |
|---|---|---|---|
| preset | combo | `Clean Spherical Prime` | See the list below |
| focal_mm | float | 35 | Range 8–300 |
| squeeze | combo | 1.0 | Choices: 1.0, 1.33, 1.5, 1.8, 2.0 |
| k1, k2, k3, p1, p2 | float | from preset | Overridable |
| ca_r, ca_b | float | from preset | Typical range ±0.003 |
| blades | int | 9 | 0 = circular |
| blade_curvature | float | 0.5 | 0 = straight edges, 1 = circle |
| cats_eye | float | 0.3 | Strength of the off-axis bokeh clipping |
| breathing | float | 0.5 | 0 = none, 1 = full thin-lens |
| profile_json | string | "" | Optional path to a lens profile; overrides the preset |

**Output:** `OO_LENS`

**Presets** are generic "looks" with documented coefficients, not reproductions of trademarked lenses:
- Clean Spherical Prime
- Vintage Spherical (stronger CA and vignette, 6 blades)
- Classic Anamorphic 2×
- Modern Anamorphic 1.5×
- Wide Rectilinear 14 mm
- Macro 100 mm
- Soft Petzval-style (high field curvature, approximated by radially increasing blur)

**Optional profiles from the lensfun database.** Lensfun data is CC-BY-SA-3.0, so it is never bundled. A separate `OpenOptics.LoadLensfunProfile` node reads a database file the user has installed.

Lensfun's `ptlens` model `r_d = r(a r³ + b r² + c r + 1 − a − b − c)` is converted to Brown-Conrady by a least-squares fit over `r ∈ [0, 1]`. The fit residual is reported in the node's output text.

### 2.3 `OpenOptics.Shot` (Setup)

| Input | Type | Default |
|---|---|---|
| camera | OO_CAMERA | — |
| lens | OO_LENS | — |
| f_number | float | 2.8 (clamped to the lens's `[f_min, f_max]`) |
| focus_m | float | 3.0 (stored internally as mm) |
| focus_curve | OO_FOCUS_CURVE | optional, from node 5 |

**Output:** `OO_SHOT`

### 2.4 `OpenOptics.FieldOfView` (Calculator)
**Outputs:** `hfov_deg`, `vfov_deg`, `dfov_deg`, `crop_factor`, `equiv_focal_ff_mm`, and `info` (STRING).

**Formulas:**
- `FOV(d) = 2·atan(d / (2f))`, with `d` = sensor width, height or diagonal.
- **Anamorphic:** horizontal FOV uses `d = squeeze · sensor_w`; vertical is unchanged.
- `crop = 43.2666 / √(w² + h²)`. 43.2666 mm is the full-frame diagonal.
- `equiv_focal = f · crop`. For anamorphic, the equivalent is computed on the desqueezed horizontal.

### 2.5 `OpenOptics.DepthOfField` (Calculator)
Gives the same numbers a DOF calculator (such as DOFMaster) would. It feeds the prompt node and the info overlay.

**Outputs:** `near_m`, `far_m` (∞ is written as `inf`), `total_m`, `hyperfocal_m`, `coc_mm`, `info`.

**Formulas (thin lens):** `f` = focal length, `N` = f-number, `s` = focus distance, `c` = CoC.
- `c = diag / 1500` unless the camera overrides it. This is the common "d/1500" criterion; `d/1730` (the Zeiss criterion) is an option.
- `H = f²/(N·c) + f`
- `D_near = s(H − f) / (H + s − 2f)`
- `D_far = s(H − f) / (H − s)` when `s < H`, otherwise `∞`
- **Anamorphic:** `c` uses the desqueezed diagonal, so the scene-space DoF matches a spherical lens of the same focal length.

### 2.6 `OpenOptics.FocusCurve` (Calculator, video)
Builds a per-frame focus distance for rack focus and pulls.

| Input | Default | Notes |
|---|---|---|
| frames | 121 | |
| keyframes | `"0:3.0, 120:1.2"` | `frame:metres` pairs |
| easing | `ease_in_out` | Options: linear, ease_in_out (cubic), hold |
| interpolate_in | `diopters` | Options: diopters, metres |

**Output:** `OO_FOCUS_CURVE` (a list of floats in mm).

**Formula:** a focus puller's lens scale is close to linear in diopters, so interpolation runs in diopters by default:
- `D = 1000/s_mm`
- interpolate `D` between keyframes
- `s = 1000/D`

### 2.7 `OpenOptics.DepthToMetric` (Image op)
Turns the output of any depth node into metric depth in mm. Sources include Depth Anything 3 in core, Video Depth Anything Small, and MoGe. The CoC maths needs real distances.

| Input | Notes |
|---|---|
| depth | IMAGE or MASK from the depth node |
| mode | One of `metric` (input already in metres; DA3-Metric, MoGe), `relative_inverse` (disparity-like; DA-V2/V3 relative), or `relative_depth` |
| near_anchor_m, far_anchor_m | For relative modes: the metric distances of the 2nd and 98th percentile depth |
| subject_mask, subject_m | Optional: pins the median depth inside the mask to `subject_m` (for example, focus on the actor) |
| temporal_smooth | 0–1, an EMA over frames on the fitted `(a, b)` only, never on pixels, so motion is preserved |

**Formulas:**
- **relative_inverse:** `Z = 1 / (a·d + b)`. `(a, b)` is solved from the two anchors: with `d₁`, `d₂` the percentiles and `Z₁`, `Z₂` the anchor distances, `a = (1/Z₁ − 1/Z₂)/(d₁ − d₂)` and `b = 1/Z₁ − a·d₁`.
- **relative_depth:** `Z = a·d + b`, fitted linearly from the same anchors.
- **metric:** `Z = 1000 · d_m`.
- All modes clamp the result to `[close_focus_mm, 1e6]`.

**Output:** `OO_DEPTH`, a float32 tensor `[B, H, W]` in mm, plus a preview IMAGE.

### 2.8 `OpenOptics.LensBlur`: physical depth of field (Image op, the core node)

| Input | Notes |
|---|---|
| image | IMAGE, one frame or a video batch |
| depth | OO_DEPTH |
| shot | OO_SHOT. If `focus_curve` is set, focus changes per frame. |
| quality | `draft` (8 depth layers), `normal` (16), `high` (32) |
| max_radius_px | Default 64. Clamps the radius for speed. |
| highlight_boost | 0–4. Expands clipped highlights before blurring so bokeh balls read as bright. |

**Formulas:**
1. **Signed CoC diameter on the sensor (thin lens):**
   `c(Z) = (f² / (N·(s − f))) · (Z − s) / Z` mm. A negative value means the point is in front of focus (near field); positive means behind (far field).
2. **In pixels:** `c_px = |c(Z)| / p = |c(Z)| · W / sensor_w`. The kernel radius is `r = c_px / 2`.
3. **Aperture kernel:**
   - A regular polygon with `blades` sides; `blades = 0` gives a circle.
   - Edges blend toward the circumscribed circle by `blade_curvature`.
   - The polygon is rotated by `blade_rotation_deg`.
   - **Anamorphic:** the kernel is scaled `1/squeeze` horizontally in the squeezed image. After desqueeze this gives the vertical oval bokeh of an anamorphic lens.
4. **Cat's-eye (optical vignetting of bokeh):** at normalised image radius `ρ`, the kernel is intersected with a second disc of the same radius, offset toward the image centre by `cats_eye · ρ · r`.
5. **Compositing (occlusion-correct, scatter-as-gather):**
   - Quantise `c` into L signed layers.
   - Blur each layer's premultiplied colour and alpha with its kernel.
   - Composite **back-to-front**: far field, then in-focus, then near field, using the "over" operator.
   - Effect: a blurred foreground spills over sharp background, and a sharp foreground edge never picks up background blur (no halo).
6. **Highlight boost:** before blurring, `L' = L · (1 + highlight_boost · smoothstep(0.8, 1.0, L))`. The blurred result is tonemapped back with `L/(1+L)` blended by the same mask.

**Output:** IMAGE (same colour space as the input) and `coc_px` as a MASK, normalised by `max_radius_px`, for debugging.

### 2.9 `OpenOptics.LensDistortion` (Image op)
Adds or removes Brown-Conrady distortion and lateral chromatic aberration.

| Input | Notes |
|---|---|
| image | |
| shot (or lens + camera) | |
| direction | `apply` (ideal → lens) or `remove` (lens → ideal) |
| fit | `crop` (zoom so no empty border), `fill_black`, or `keep` |

**Formulas:**
- **Normalised coordinates:** `x = (u − c_x)/f_px`, `y = (v − c_y)/f_px`, and `r² = x² + y²`.
- **Distortion:**
  - `radial = 1 + k1 r² + k2 r⁴ + k3 r⁶`
  - `x_d = x·radial + 2 p1 x y + p2 (r² + 2x²)`
  - `y_d = y·radial + p1 (r² + 2y²) + 2 p2 x y`
- **Apply (inverse warp):** for each output pixel at distorted position `(x_d, y_d)`, solve for `(x, y)` by fixed-point iteration (`x ← (x_d − Δx(x,y)) / radial(x,y)`, 8 iterations, stopping when the change is below `1e-6`). Then sample the input with bilinear interpolation (bicubic is an option).
- **Remove:** forward-evaluate the formula above and sample.
- **Lateral CA:** per-channel radial scale applied on top. The R channel samples at `(x, y)·(1 + ca_r)` and B at `(x, y)·(1 + ca_b)`; G is the reference.
- **Anamorphic:** the distortion runs on desqueezed coordinates (`x` scaled by `squeeze`), then the result is re-squeezed.
- **crop fit:** zoom `z = 1/min(r_valid)`, the largest uniform scale that keeps every output pixel inside the source. It is found by a 64-sample search along the border.

### 2.10 `OpenOptics.Vignette` (Image op)

**Formulas** (multiplied together, in linear light):
- **Natural vignetting (cos⁴ law):**
  - `r_mm = p · √((u − c_x)² + (v − c_y)²)`
  - `θ = atan(r_mm / f)`
  - `V_nat = cos⁴ θ`
- **Mechanical vignetting:**
  - `V_mech = 1 − v_eff · smoothstep(0.55, 1.0, ρ)`
  - `ρ` is the radius normalised to the half-diagonal.
  - `v_eff = vig_mech · clamp((N_stop − N)/(N_stop − f_min), 0, 1)`, with `N_stop = f_min · 2^(vig_stop_out/2)`.
  - Effect: vignetting fades out as you stop down by `vig_stop_out` stops (default 2).

| Input | Default |
|---|---|
| natural | on |
| mechanical | on |
| strength | 1.0 (a creative global multiplier on the log-exposure offset: `V^strength`) |

### 2.11 `OpenOptics.Anamorphic` (Image op)
- **mode = `desqueeze`:** resize the width by `× squeeze` (Lanczos), or resize the height by `÷ squeeze` (`keep_width` option).
- **mode = `squeeze`:** the inverse.
- **Streak flare:**
  - Highlights: `M = max(0, L − T)`, with threshold `T` = 0.9 linear by default.
  - Convolve horizontally with `k(x) = exp(−|x|/λ)`, where `λ = flare_length · W`.
  - Tint by `flare_tint_rgb`, scale by `flare_strength`, and add.
  - Output: `L' = L + strength · tint · (M ∗ k)`.

### 2.12 `OpenOptics.FocusBreathing` (Image op, video)
Changes image magnification as focus changes, the way real lenses "breathe".

- **Thin lens, magnification relative to infinity focus:** `m(s) = v(s)/f = s/(s − f)`.
- **Per frame:** `scale_t = (m(s_t)/m(s_ref))^β`, with `β = lens.breathing`.
  - `s_ref` is the first frame's focus distance.
  - Each frame is centre-scaled by `scale_t`, with Lanczos resampling and cropping back to W×H.

### 2.13 `OpenOptics.ShotToPrompt` (Integration)
Writes the shot as prompt text. This is the Higgsfield-style "picker" output.

**Example:** `"shot on a 35mm lens at f/2.8, shallow depth of field, focus at 3 m (sharp from 2.7 m to 3.3 m), horizontal field of view 39°, 2x anamorphic, oval bokeh"`

- Phrases come from a template table in `presets/prompt_phrases.json`.
- Thresholds: DoF under 1 m reads "shallow"; DoF of 10 m or more, or a far limit of ∞, reads "deep focus".
- Prompts carry little weight with LTX (research §4), so this node is supplementary. The physical ops do the real work.

**Outputs:** `positive` (STRING) and `negative` (STRING). The negative prompt is, for example, "fisheye" when the lens is rectilinear.

### 2.14 `OpenOptics.CameraMove` (Integration)
Maps a move preset to model-specific conditioning.

| Input | Options |
|---|---|
| move | static, dolly_in, dolly_out, truck_left, truck_right, jib_up, jib_down |
| target | `ltx2_lora` or `wan_camera_embed` |
| speed | Speed of the move |

- **`ltx2_lora`:** outputs the LoRA filename and its strength. The user applies it with a standard `LoraLoaderModelOnly`.
  - Hugging Face repo: `Lightricks/LTX-2-19b-LoRA-Camera-Control-<Move>`.
  - ComfyUI's own LTX-2 template expects the lowercase local filename `ltx-2-19b-lora-camera-control-<move>.safetensors`.
- **`wan_camera_embed`:** outputs the parameters for core `WanCameraEmbedding`.
- **`focal_mm` link:** a dolly move can optionally be linked to the shot's focal length, which enables a **dolly-zoom (vertigo)** helper.
  - Keep subject size constant: `f_t = f_0 · d_t / d_0`, where `d` is the camera-to-subject distance.
  - It emits a per-frame focal list that `LensDistortion`, `Vignette` and `FocusBreathing` accept.

---

## 3. Recommended chain (example workflow shipped with the pack)

```
LTX / Wan generate ─► [frames]
                        │
DA3 or VideoDepthAnything-Small ─► DepthToMetric ─┐
                        │                          │
CameraBody ─► Shot ◄─ Lens       FocusCurve ───────┤
                        │                          │
            frames ─► LensBlur ◄───────────────────┘
                   ─► FocusBreathing
                   ─► LensDistortion (apply, + lateral CA)
                   ─► Vignette
                   ─► Anamorphic (streak flare, desqueeze)
                   ─► Save
Shot ─► ShotToPrompt ─► text encoder (before generation)
Shot ─► CameraMove ─► LoRA loader / WanCameraEmbedding (before generation)
```

**Why this order:**
- Defocus happens in scene space, so it comes first.
- Distortion and CA are a geometric remap of the image plane.
- Vignetting is an illumination falloff at the sensor.
- The flare is added last, on top of the image.

The example workflow runs headless through the **Comfy SDK** (`comfy-sdk` against a `comfy-api-proxy` in front of local ComfyUI). This meets the competition's Comfy Developer Platform requirement.

---

## 4. Test plan

Tooling:
- `pytest` for logic.
- `torch.testing.assert_close` for tensors.
- Golden images compared by SSIM, never by hash.
- Every test runs on CPU in CI; GPU tests are marked `@pytest.mark.gpu` and run locally on the 3090.

Reference values below were computed analytically for this spec. A test passes within the tolerance shown.

### C. Calculators (exact maths)
| ID | Case | Expected |
|---|---|---|
| C1 | Camera presets | Each preset's w/h matches the cited data sheet (citations added in `cameras.json`). Review step, not automated. |
| C2 | FOV: 50 mm, full frame 36×24 | HFOV 39.598°, VFOV 26.991°, DFOV 46.793° (±0.001°) |
| C3 | FOV: 50 mm 2× anamorphic, 22 mm-wide gate | HFOV 47.499° (spherical would be 24.815°) |
| C4 | Crop factor, Super 35 (24.89×18.66) | 1.3909 |
| C5 | DoF: f = 50, N = 2.8, s = 3 m, c = 43.2666/1500 = 0.028844 mm | H = 31.004 m, near = 2.7390 m, far = 3.3160 m, total = 0.5771 m (±0.1 mm) |
| C6 | DoF at and beyond hyperfocal | s = H: near = H/2 exactly; s > H: far = ∞ and near = s(H−f)/(H+s−2f) |
| C7 | Cross-check | 20 random (f, N, s, c) cases agree with an independent closed-form implementation written in the test file, rel. error < 1e-9 |
| C8 | FocusCurve diopter interpolation, 3 m → 1.2 m over 121 frames, linear | Frame 60: D = (1/3 + 1/1.2)/2 = 0.58333 m⁻¹ → s = 1.7143 m (±0.1 mm) |
| C9 | FocusCurve endpoints and monotonicity | Frames 0 and 120 equal the keyframes exactly; the curve is strictly monotone for a 2-key pull |

### B. LensBlur
| ID | Case | Expected |
|---|---|---|
| B1 | CoC formula: f = 50, N = 2.8, s = 3 m, Z = ∞ | `c` = 0.30266 mm, which is **10.76 px** at W = 1280 on a 36 mm sensor |
| B2 | Symmetry property | `c(Z = 1.5 m) = c(∞)` for `s = 3 m` (both 0.30266 mm); `c(6 m) = c(∞)/2` |
| B3 | In-focus plane | A pixel at `Z = s` is unchanged (max abs diff < 1e-6) |
| B4 | Synthetic point-light grid: single-pixel lights on black at known Z | The measured bokeh disc diameter (threshold at 50 % of the plateau) equals `c_px` within ±1 px, for 5 depths × 3 f-stops |
| B5 | Aperture shape | With `blades = 6` and `curvature = 0`, the disc's convex hull has 6 corners (polygon fit); rotation matches `blade_rotation_deg` ±2° |
| B6 | Anamorphic | Bokeh aspect ratio (h/w) in the squeezed image equals `squeeze` ±3 % |
| B7 | Occlusion: sharp foreground bar at s against a far-blurred textured background | No background colour bleeds into the bar: a 3-px band inside the bar edge stays within 1 % of the original |
| B8 | Near-field spill: blurred near object over a sharp far wall | Blur extends **over** the wall by `r_px` ±1 px |
| B9 | Energy | Mean linear luminance is conserved within 0.5 % on a uniform-depth scene (highlight_boost = 0) |
| B10 | Video stability: static frames with constant shot | Frame-to-frame output diff is 0 |
| B11 | Rack focus | With a FocusCurve, the per-frame `coc_px` mask follows the curve; spot-checked at 3 frames against the formula |
| B12 | Performance (GPU) | 1280×720, 121 frames, `normal` quality: under 90 s on the RTX 3090 (target, recorded in benchmarks.md) |

### D. LensDistortion / CA
| ID | Case | Expected |
|---|---|---|
| D1 | Formula vector: `k1 = −0.1, k2 = 0.01`, `(x, y) = (0.5, 0.3)` | `(x_d, y_d)` = (0.483578, 0.290147) |
| D2 | Round trip: apply then remove, k1 ∈ [−0.3, 0.3] | Interior pixel RMS error < 0.5 / 255; coordinate round-trip error < 0.01 px |
| D3 | OpenCV parity (test-only dependency, Apache-2.0) | Point mapping matches `cv2.projectPoints` with the same `(k1, k2, p1, p2, k3)` to < 1e-5 normalised units |
| D4 | Straight-line test: a grid of straight lines with negative k1 | Lines bow outward (barrel). With `remove`, the line-straightness residual (RMS distance to a fitted line) is < 0.2 px |
| D5 | Zero coefficients | Output equals the input exactly (identity fast path) |
| D6 | Lateral CA | A white dot at the image corner shows an R/B offset of `ρ·W/2·ca` px ±0.5 px; the centre dot has no offset |
| D7 | `crop` fit | No pixel samples outside the source (no black border) for k1 ∈ [−0.3, 0.3] |

### V. Vignette
| ID | Case | Expected |
|---|---|---|
| V1 | Natural, 24 mm on full frame, corner | `θ` = 42.031°, gain = 0.30440 (−1.716 stops) ±1e-4 |
| V2 | Natural, 50 mm on full frame, corner | gain = 0.70950 |
| V3 | Centre pixel | gain = 1.0 |
| V4 | Mechanical stop-out | At `N ≥ f_min · 2^(vig_stop_out/2)`, `V_mech = 1` everywhere |
| V5 | Linear-light check | The vignette applied to an sRGB-encoded mid-grey equals the decoded value × gain, then re-encoded |

### A. Anamorphic, breathing, misc.
| ID | Case | Expected |
|---|---|---|
| A1 | Desqueeze 2× | 1280×720 becomes 2560×720 (or 1280×360 with `keep_width`) |
| A2 | Streak flare | A single bright pixel gives a horizontal streak whose profile matches `exp(−|x|/λ)`, R² > 0.99; there is no vertical spread |
| A3 | Below-threshold image | Flare adds 0 |
| F1 | Breathing magnification | f = 50, s = 1 m: m = 1.05263; f = 85, s = 0.5 m: m = 1.20482 |
| F2 | β = 0 | Output equals input |
| F3 | Dolly-zoom helper | `f_t · d_0 = f_0 · d_t` for all frames; the subject bounding box in a synthetic render stays constant ±1 % |
| M1 | DepthToMetric `relative_inverse` | The two anchors map exactly to `near_anchor_m` and `far_anchor_m` |
| M2 | DepthToMetric temporal smoothing | Changes `(a, b)` only; a static input sequence gives an identical output |
| M3 | sRGB round trip | `encode(decode(x)) = x` within 1e-6 over [0, 1] |
| P1 | ShotToPrompt | A golden-string test per preset; "shallow" and "deep focus" thresholds follow §2.13 |

### I. Integration
| ID | Case | Expected |
|---|---|---|
| I1 | ComfyUI load | Headless ComfyUI imports the pack. `/object_info` lists all 14 nodes. Missing optional dependencies give a warning, not a crash. |
| I2 | Example workflow via the Comfy SDK | `comfy-sdk` → `comfy-api-proxy` → local ComfyUI runs `workflows/open_optics_demo.json` end to end, and the output file exists |
| I3 | Golden render | A fixed input frame plus depth through the full chain stays at SSIM ≥ 0.995 against the stored reference |
| I4 | VRAM | The full post chain on 121 frames at 720p peaks below 6 GB, so it runs after the video model is unloaded |
| I5 | Licence hygiene | CI check: no file is copied from GPL, AGPL or unlicensed packs (named in research.md §3). The lensfun DB is not vendored. `LICENSE` exists. |

---

## 5. Repo layout (planned)

```
open-optics/
  __init__.py            # NODE_CLASS_MAPPINGS
  pyproject.toml         # Comfy Registry metadata
  LICENSE
  open_optics/
    types.py             # OO_CAMERA / OO_LENS / OO_SHOT dataclasses
    optics.py            # pure maths: fov, dof, coc, breathing (no torch)
    colour.py            # sRGB <-> linear
    blur.py              # layered gather DOF
    distortion.py        # Brown-Conrady, CA
    vignette.py, anamorphic.py, depth.py, prompt.py, camera_move.py
    nodes/*.py           # thin ComfyUI wrappers over the above
  presets/cameras.json, lenses.json, prompt_phrases.json
  workflows/open_optics_demo.json
  tests/
```

The pure maths in `optics.py` has no torch import. Tests C1–C9 and F1 therefore run instantly and can be checked by hand.

---

## 6. Open questions
1. **Pack licence.** The candidates are MIT, Apache-2.0 and GPL-3.0.
   - Apache-2.0 adds a patent grant.
   - GPL-3.0 would let us learn from GPL packs such as NKD.
   - The decision is needed before writing code.
2. **Video depth source for the demo.** Video-Depth-Anything-Small (Apache-2.0) is temporally stable. Core DA3 Small/Base runs per frame. Benchmark both for flicker.
3. **v2 candidates:** longitudinal (axial) CA tied to the sign of the CoC; field curvature; bokeh "onion rings"; per-lens breathing curves instead of a single β.
4. **GLSLShader.** Should we also ship GLSL versions of the cheap ops (vignette, CA) for the core `GLSLShader` node?
