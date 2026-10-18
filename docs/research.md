# Open Cinema — Research

Research for an open rebuild of Higgsfield Cinema Studio, entered in Comfy's developer-platform challenge.
Compiled 2026-10-17. Every fact has a source next to it.

Tags:
- **[C]** confirmed from an official page, a model card, a LICENSE file or the GitHub API.
- **[U]** unverified: a third-party page, a community anecdote, or an inference.
- Licences and push dates come from the GitHub API (`api.github.com/repos/...`), checked 2026-10-17.
- Reddit was not readable with the fetch tooling, so community reports from r/comfyui and r/StableDiffusion are under-sampled.

---

## TL;DR

1. **The challenge has a new name and a new deadline.** The "Comfy Dev Platform Challenge" is now **"Open Source Higgsfield"**. Submissions close **Friday, October 30, 2026, 9:00 AM PT**. Winners will be announced **November 6**. Cinema Studio is named explicitly as a target app. **Hard requirement:** the app must be built on the Comfy Developer Platform (Comfy Router and/or Comfy SDK), and the repo must have an open-source licence.
2. **LTX on a 24GB RTX 3090:**
   - The **0.9.x models (2B and 13B)** fit natively.
   - The **22B models (LTX-2.3 and 2.5)** run only with GGUF quantisation plus CPU offload. Officially they need 32GB+.
   - **Official camera-move LoRAs** (dolly in/out/left/right, jib up/down, static) exist only for **LTX-2 19B**.
   - On LTX-2.5, camera moves come from the Layout-To-Render IC-LoRA (it copies the camera from a 3D blocking video). The 0.9.x models have no camera LoRAs.
3. **Plenty of depth, DOF, lens-FX and camera nodes exist, but their licences vary a lot:**
   - Several popular packs have **no LICENSE file**, which legally means all rights reserved.
   - **DepthCrafter's node code is non-commercial.**
   - **ComfyUI-LTXVideo moved off Apache-2.0** to the LTX-2 Community License.
   - ComfyUI core now ships nodes for Depth Anything 3, MoGe, Lotus, Marigold and Wan camera control.
4. **No comprehensive, physically based lens/optics pack exists.** Pieces are scattered across small packs:
   - CoC bokeh in RealisticBokeh.
   - Real lens profiles in Darkroom.
   - Anamorphic squeeze in NKD.

   No pack has a shared camera/lens data type that drives both the prompt and the physical post-processing. Every open "Higgsfield clone" just turns the picker into prompt words. **This is the gap to fill.**

---

## 1. Competition: deadline and rules

### Identity and status
- The challenge opened Oct 1 as the **"Comfy Dev Platform Challenge"**, with a window of Oct 5–19. Its page now returns 404: https://blog.comfy.org/p/open-call-comfy-dev-platform-challenge [C: 404 observed].
- It now runs as **"Open Source Higgsfield"**, with the window extended to Oct 30.
  - The rename is stated explicitly only by comfyui-wiki: https://comfyui-wiki.com/en/news/2026-10-01-comfy-dev-platform-challenge (2026-10-15 article) [U].
  - Supporting evidence: the official Typeform submission form was published 2026-10-05, the old challenge's start date, and last updated 2026-10-14, the day before the Higgsfield launch [C: Typeform metadata].
  - No official Comfy text says "renamed" or "extended" in those words.

### Official links [C]
- Competition page (rules): https://comfy.org/open-source-higgsfield/ (a zh-CN version also exists)
- Announcement: https://blog.comfy.org/p/higgsfield-promised-to-open-source (Allyson Toy, Oct 15, 2026)
- Sign-up: https://form.typeform.com/to/Ayn9Cwfj
- Submission: https://form.typeform.com/to/V1dSQrkS
- Example apps: https://comfy.org/hub/apps/
- SDK docs: https://docs.comfy.org/development/api-development/sdks
- Build Nights: SF https://luma.com/5mydmvu6 · LA https://luma.com/73q6c0ln

### Dates [C] (source: comfy.org/open-source-higgsfield/ and the submission form)
| Event | Date |
|---|---|
| Registration opens | Oct 15, 2026 |
| Build window | Oct 15 – Oct 30 |
| **Submission deadline** | **Friday Oct 30, 2026, 9:00 AM PT** |
| Build Night SF (Frontier Tower) | Oct 28 |
| Build Night LA (with AI On The Lot) | Oct 29 |
| Winners announced | Nov 6 (featured on comfy.org/hub) |

The Build Nights are optional and separate from the online competition. No separate judging period is published.

### App requirements [C]
1. The app must be built with the **Comfy Developer Platform (Comfy Router and/or Comfy SDK)**.
2. The repo must have an **open-source licence** and enough setup detail for someone else to run it locally.
3. Other tools, models and techniques are allowed, but they **must be explained in the demo video**.
4. Entries must be lawful and SFW, with no unlicensed IP or likenesses.
5. By submitting, you let ComfyUI, NVIDIA, Runpod, LTX, Black Forest Labs and MiniMax feature the work with credit.
6. **One submission per person.** No team-size rule is published.

### Deliverables [C]
- **GitHub repo:** app code, workflow files, open-source licence, and instructions to run it locally.
- **Demo video:** 2 minutes max. "We're judging the work, not your video editing."
- **Link to try it:** optional but strongly encouraged. It is not shared publicly; expect 5–10 judging runs.
- **Social post:** must link the demo video and use **#OpenSourceHiggsfield** (Reddit, X, IG, LinkedIn, YT or TikTok).

### Submission form fields [C] (https://form.typeform.com/to/V1dSQrkS)
- Name, the email on your Comfy app account, country.
- ComfyUI familiarity.
- Project name and a one-liner of at most 100 characters.
- Public GitHub URL and demo video URL.
- "Which parts of ComfyUI did you use?" Options: Comfy API, Router, SDK, Cloud Agent, Local Agent, MCP.
- "List all generative models used."
- Category. Options: Most Innovative, Most Viral, Open Weights Only, Built with FLUX 3 Bonus, VFX Built with LTX Bonus. The form has **no MiniMax H3 option**, although the page lists that bonus.
- "Is your stack fully open?" The form defines this as every model, node and dependency being open-weights or open-source, with no closed API model in the critical path. Rented GPUs still count.
- Four agreements.

### Prizes ($25,000 total) [C]
| Category | Prize | Criterion (verbatim summary) |
|---|---|---|
| Best Overall | $10,000 | Every entry is considered automatically |
| Most Innovative | RTX 5090 | Something never done before; "novel custom node packs"; the video must explain why it is innovative |
| Most Viral | RTX 5090 | Delightful to use and made to be shared |
| Open Weights Only | RTX 5090 | No partner nodes or closed APIs; open-weights models only |
| 10 runners-up | $250 Comfy Credits each | — |
| Bonus: VFX built with LTX | $2,000 cash | LTX is the core video model |
| Bonus: Built with FLUX 3 | $1,000 / $500 / $250 in Flux API credits | FLUX 3 is the core model |
| Bonus: Built with MiniMax H3 | $1,000 in API credits | H3 is the core model |

- Each entry can win **one main category and one model-provider bonus**.
- The first 200 sign-ups get free credits.

### Not published
- Judging criteria and weights, named judges, eligibility (age or country), and full legal terms. The footer links only the general ToS.
- Old challenge criteria, as reported by comfyui-wiki [U]:
  - The panel came from ComfyUI, NVIDIA and Runpod.
  - "Most Practical" was scored on real-world usefulness, completeness and reproducibility.
  - These may still guide the judges.

### Implications for this project
- Cinema Studio is named explicitly. The example apps already include "Cinematic Studio – Direct your shot like a film set" and "Re-shoot a video" (https://comfy.org/hub/apps/). **We need clear differentiation**, and physical optics is the obvious angle.
- A novel lens/optics node pack fits **Most Innovative** ("novel custom node packs").
- An all-open stack (LTX weights plus open nodes) could also enter **Open Weights Only** and the **LTX VFX bonus**.
- Check that the LTX-2 Community License counts as "open-weights" for that category. It is a source-available licence with a revenue threshold, not OSI-approved.
- The Comfy Router/SDK requirement is mandatory. The architecture has to go through it.

---

## 2. LTX models on a 24GB RTX 3090, and camera-motion control

The 3090 is Ampere: bf16/fp16 are fine, but there is **no FP8 compute**.
- FP8 checkpoints load weight-only and are upcast. This saves memory, not time.
- `fp8-scaled-mm` needs Hopper or newer, and NVFP4 needs Blackwell (https://github.com/Lightricks/LTX-2, https://huggingface.co/Lightricks/LTX-2.5) [C].

| Version | Release | Size | Licence | Fits 24GB 3090? | Camera control |
|---|---|---|---|---|---|
| 0.9.0 / 0.9.1 | Nov / Dec 2024 [C] | 2B | Per-version (OpenRail-M family) [C] | **Yes** [U: no measured numbers] | None |
| 0.9.5 / 0.9.6 | Mar / Apr 2025 [C] | 2B | Open-Weights 0.X [C] | **Yes**, "light VRAM" [C] | Keyframes only |
| 0.9.7 13B (dev / distilled / fp8) | May 2025 [C] | 13B | Open-Weights 0.X [C] | **Yes**, especially distilled or GGUF [U] | IC-LoRA Depth/Pose/Canny (Jul 2025) and keyframes [C]. No camera LoRAs |
| 0.9.8 | Jul 16 2025 [C] | 13B / 2B | Open-Weights 0.X [C] | **Yes** [U] | IC-LoRAs and the detailer; clips up to 60 s [C] |
| **LTX-2** | Weights Jan 2026 [C] | 19B, audio+video | LTX-2 Community License [C] | **Tight.** Official guidance is 32GB+ [C]. One "~2 min / 120 frames" 3090 report has no clear source [U] | **7 official camera LoRAs** plus IC-LoRA Depth/Pose/Canny/Union/Detailer [C] |
| LTX-2.3 | Mar 2026 [U] | 22B | LTX-2 Community License [C] | **With quantisation and heavy offload.** Community reports about 7–10 min per clip; a ComfyUI regression pushed one case to 40+ min [U] | The 19B camera LoRAs are listed in the 2.3 doc, but compatibility is unconfirmed [U]. IC-LoRA Union and Motion-Track [C] |
| **LTX-2.5** (latest) | Aug 11 2026 [C/U] | 22B | LTX-2.x Community License: free under $10M annual revenue [C] | **With GGUF Q5_K_M/Q6_K and offload.** 8 s at 960×544, upscaled to 1080p, took about 7 min [U] | No preset camera LoRA. **Layout-To-Render IC-LoRA** copies the camera from a Blender/Unreal playblast [C]. Keyframe interpolation [C] |

### Official camera LoRAs (LTX-2 19B) [C]
Collection: https://huggingface.co/collections/Lightricks/ltx-2

- `Lightricks/LTX-2-19b-LoRA-Camera-Control-Dolly-In`
- The same base name ending in `-Dolly-Out`, `-Dolly-Left`, `-Dolly-Right`, `-Jib-Up`, `-Jib-Down` or `-Static`.

Usage, per the model card (https://huggingface.co/Lightricks/LTX-2-19b-LoRA-Camera-Control-Dolly-In):
- Strength 1.0.
- No trigger word; describe where the move ends up.
- Loads with a standard LoRA loader in ComfyUI.

Other camera options:
- Community option for 2.3: `elismasilva/LTX-2.3-LoRa-Camera-Controls`, covering pan, tilt and zoom. It is experimental and **non-commercial** [U] (https://huggingface.co/elismasilva/LTX-2.3-LoRa-Camera-Controls).
- Layout-To-Render IC-LoRA for 2.5: https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Layout-To-Render [C].
- Motion-Track IC-LoRA for 2.3 (point trajectories, not camera): https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Motion-Track-Control [C].

### Practical 3090 recipe [U]
- Use a GGUF Q5_K_M or Q6_K transformer through ComfyUI-GGUF: https://civitai.com/models/2871770/joy-ltx-25-distilled-gguf-int8-nvfp4-w4a8-mix4x8
- Use the distilled model at 8 steps.
- Use the low-VRAM loaders plus `--reserve-vram` (https://github.com/Lightricks/ComfyUI-LTXVideo).
- Have 64GB+ system RAM.
- Pin a known-good ComfyUI version, because of the regression in https://github.com/Comfy-Org/ComfyUI/issues/14345.

The **text encoder costs a lot of memory**:
- LTX-2 and 2.3 use Gemma 3 12B, reported at about 24–27GB (https://github.com/Lightricks/ComfyUI-LTXVideo/issues/303).
- LTX-2.5 uses Gemma 4 12B, about 14.6GB (https://huggingface.co/guillaume127/LTX-2.5-FP8).
- Unload the encoder before sampling.

### Decision hints
- **For preset moves** (dolly, jib, static) on a 3090, LTX-2 19B with the official camera LoRAs is the most direct route, if it fits with quantisation.
- **For arbitrary camera paths**, use one of two routes:
  - (a) Render a depth or blocking pass along our own camera path, then drive LTX-2.5 Layout-To-Render or IC-LoRA Depth.
  - (b) Use Wan Fun Camera, which has an Apache-2.0 licence and a native `WanCameraEmbedding` node (§3.4).
- Check the measured 3090 timings ourselves early. No credible measured numbers exist for 0.9.x or for LTX-2 19B.

### Conflicts noted
- Some third-party pages call LTX-2.3 "Apache-2.0", but the HF cards say LTX-2 Community License. **Trust the cards.**
- The LTX-2.5 Diffusers repo is tagged 19B, while its filenames say 22B.

### Sources
- https://github.com/Lightricks/LTX-Video
- https://huggingface.co/Lightricks/LTX-Video
- https://github.com/Lightricks/LTX-2
- https://github.com/Lightricks/LTX-2/blob/main/MODELS-LTX-2.3.md
- https://huggingface.co/Lightricks/LTX-2
- https://huggingface.co/Lightricks/LTX-2.3
- https://huggingface.co/Lightricks/LTX-2.5
- https://docs.ltx.video/open-source-model/getting-started/system-requirements
- https://github.com/Lightricks/ComfyUI-LTXVideo
- https://www.nvidia.com/en-gb/geforce/news/rtx-ai-video-generation-guide
- https://localaimaster.com/blog/local-ai-video-generation [U]
- https://datanorth.ai/news/ltx-releases-ltx-2-5-open-weights-video-world-model [U]
- https://invoke.ai/configuration/fp8-storage/

---

## 3. Existing open-source ComfyUI nodes, with licences

Licence key:
- A **None** entry means there is no LICENSE file, so the code is all rights reserved by default. **Don't copy code from it.**
- The node licence and the model-weight licence are often different. Both are listed.
- GPL-3.0 and AGPL-3.0 bind derived code.

**ComfyUI core** (https://github.com/Comfy-Org/ComfyUI, GPL-3.0, pushed 2026-10-18 UTC) now ships natively [C]:
- Depth Anything 3: `LoadDA3Model`, `DA3Inference`, `DA3Render`, plus mesh and point cloud output.
- MoGe: including panorama and `MoGeGeometryToFOV`.
- `LotusConditioning` and `MarigoldV2PostProcess`.
- Camera: `WanCameraEmbedding`, `WanCameraImageToVideo`, `WanTrackToVideo`/WanMove, and `CreateCameraInfo` + `CameraAngle` (added 2026-10-06).
- An experimental **`GLSLShader`** image node, which could host lens shaders.
- Core has **no** DOF, chromatic-aberration, vignette or grain nodes.

### 3.1 Depth estimation
| Repo | Node licence | Model-weight caveat | Last push | Notes |
|---|---|---|---|---|
| ComfyUI core | GPL-3.0 | DA3-Large/Giant/Nested: **CC-BY-NC-4.0**. DA3-Small/Base/Metric-Large/Mono-Large: Apache-2.0. MoGe: MIT. Lotus: Apache-2.0. Marigold v1.1: OpenRAIL++ | 2026-10-18 | The best base to build on |
| [Fannovel16/comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux) | Apache-2.0 | DA-V2 Base/Large: CC-BY-NC (Small: Apache). Metric3D: BSD-2 | 2026-10-11 | MiDaS, LeReS, Zoe, DA V1/V2, **Metric3D**. 2.75M downloads |
| [kijai/ComfyUI-DepthAnythingV2](https://github.com/kijai/ComfyUI-DepthAnythingV2) | **None** | V2 Base/Large: CC-BY-NC | 2026-03-06 | Simple DA-V2 |
| [PozzettiAndrea/ComfyUI-DepthAnythingV3](https://github.com/PozzettiAndrea/ComfyUI-DepthAnythingV3) | MIT | DA3 split as above | 2026-08-24 | 474★ |
| [1038lab/ComfyUI-Depth-Anything-3](https://github.com/1038lab/ComfyUI-Depth-Anything-3) | GPL-3.0 | DA3 split | 2026-10-02 | New |
| [kijai/ComfyUI-Marigold](https://github.com/kijai/ComfyUI-Marigold) | GPL-3.0 | OpenRAIL++ | 2025-05-16 | Superseded by core |
| [spacepxl/ComfyUI-Depth-Pro](https://github.com/spacepxl/ComfyUI-Depth-Pro) | Apache-2.0 | **Apple AMLR (research only)** | 2024-10 (stale) | Metric depth and **focal length estimate** |
| [akatz-ai/ComfyUI-DepthCrafter-Nodes](https://github.com/akatz-ai/ComfyUI-DepthCrafter-Nodes) | **Tencent: non-commercial, research only (the code too)** | Tencent "other" | 2025-05-05 | Temporally consistent video depth |
| [yuvraj108c/ComfyUI-Video-Depth-Anything](https://github.com/yuvraj108c/ComfyUI-Video-Depth-Anything) | Apache-2.0 | VDA-Large: CC-BY-NC. VDA-Small: Apache-2.0 | 2026-01-08 | Long-video depth. **The Small model is the commercially safe option** |
| [zade23/ComfyUI-MoGe2](https://github.com/zade23/ComfyUI-MoGe2) / [PozzettiAndrea/ComfyUI-MoGe2](https://github.com/PozzettiAndrea/ComfyUI-MoGe2) | MIT / MIT | MIT | 2026-03 / 2026-08 | Point maps and **intrinsics/FoV** |
| [kijai/ComfyUI-MoGe](https://github.com/kijai/ComfyUI-MoGe) | **None** | MIT | 2025-02 (stale) | — |
| [kijai/ComfyUI-Lotus](https://github.com/kijai/ComfyUI-Lotus) | **None** | Apache-2.0 | 2025-11-04 | — |
| [PozzettiAndrea/ComfyUI-Lotus2](https://github.com/PozzettiAndrea/ComfyUI-Lotus2) | Apache-2.0 | Unverified | 2026-08-22 | — |
| [akatz-ai/ComfyUI-Depthflow-Nodes](https://github.com/akatz-ai/ComfyUI-Depthflow-Nodes) | **AGPL-3.0** | Uses your depth map | 2026-02-15 | 2.5D parallax camera moves with DOF and vignette. The BrokenSource/ComfyUI-DepthFlow repo returns 404 |

### 3.2 Depth of field, bokeh and lens blur
| Repo | Node licence | Last push | Notes |
|---|---|---|---|
| [WASasquatch/was-node-suite-comfyui](https://github.com/WASasquatch/was-node-suite-comfyui) (v3) | MIT | 2026-10-17 | Image fDOF Filter (depth input, gaussian/box modes) plus lens distortion, chromatic aberration (CA), vignette and grain |
| [digitaljohn/comfyui-propost](https://github.com/digitaljohn/comfyui-propost) | MIT | 2025-02-10 | **Depth Map Blur**, radial blur, grain, vignette, LUT |
| [chflame163/ComfyUI_LayerStyle](https://github.com/chflame163/ComfyUI_LayerStyle) | MIT | 2026-10-10 | Film/FilmV2 takes `depth_map` and `focal_depth` for defocus |
| [marcsole96/ComfyUI-RealisticBokeh](https://github.com/marcsole96/ComfyUI-RealisticBokeh) | MIT | 2026-09-05 | **Physical CoC** from focal length, f-stop, sensor width and metric focus distance. Polygon and oval bokeh, cat's-eye vignetting. 1★ |
| [Nekodificador/ComfyUI-NKD-VFX-Tools](https://github.com/Nekodificador/ComfyUI-NKD-VFX-Tools) | GPL-3.0 | 2026-10-11 | Lens Blur (depth, click-to-focus, aperture); whether it is physically based is unverified |
| [EricRollei/comfyui-refocus](https://github.com/EricRollei/comfyui-refocus) | Apache-2.0 | 2026-05-04 | Generative refocus. Depends on FLUX.1-dev (non-commercial) and DepthPro (Apple AMLR) |
| [esperandoelrender/ComfyUI-ER-VFX-Nodepack](https://github.com/esperandoelrender/ComfyUI-ER-VFX-Nodepack) | MIT | 2026-09-16 | Camera Defocus with N-blade bokeh. Radius is a % of width, not physical |
| [skatardude10/ComfyUI-Optical-Realism](https://github.com/skatardude10/ComfyUI-Optical-Realism) | **None** | 2026-04-29 | f-stop preset DOF ("TESTING"), not true CoC |
| [greatdaytoyou/lens-bokeh-blur](https://github.com/greatdaytoyou/lens-bokeh-blur) | GPL-3.0 | 2024-12 | 0★ |
| [jrabek/BokehDiffusionComfyUI](https://github.com/jrabek/BokehDiffusionComfyUI) | **None** | 2025-11 | — |
| [spacepxl/ComfyUI-Image-Filters](https://github.com/spacepxl/ComfyUI-Image-Filters) | MIT | 2025-12-15 | No DOF node. Guided blur, depth-to-normals, BetterFilmGrain |
| [Amorano/Jovimetrix](https://github.com/Amorano/Jovimetrix) | MIT (+ joke line) | 2025-09-05 | Blur and GLSL nodes |

### 3.3 Lens distortion, CA, vignette, grain, film
| Repo | Node licence | Last push | Notes |
|---|---|---|---|
| [jeremieLouvaert/ComfyUI-Darkroom](https://github.com/jeremieLouvaert/ComfyUI-Darkroom) | **README says MIT, but there is no LICENSE file** | 2026-10-05 | Most complete: **Lens Profile with 102 real lenses**, Brown-Conrady distortion, CA, vignette, halation, 161 film stocks. **Ask the author to add a LICENSE before reusing any code** |
| [Nekodificador/ComfyUI-NKD-VFX-Tools](https://github.com/Nekodificador/ComfyUI-NKD-VFX-Tools) | GPL-3.0 | 2026-10-11 | Lens Distort: barrel/pincushion, CA, vignette, **anamorphic squeeze**, solve-from-lines, fSpy camera solve |
| WAS v3 (above) | MIT | 2026-10-17 | Lens Distortion, CA, Vignette, Film Grain |
| [EllangoK/ComfyUI-post-processing-nodes](https://github.com/EllangoK/ComfyUI-post-processing-nodes) | GPL-3.0 | 2025-01-20 | CA (channel shift), grain, glow |
| [Guillaume-127/ConfyUI_Post_Processing_PRO](https://github.com/Guillaume-127/ConfyUI_Post_Processing_PRO) | GPL-3.0 | 2026-04-14 | Brown-Conrady distortion, lateral CA, veiling glare, halation |
| [cyco-creates/Flarecore](https://github.com/cyco-creates/Flarecore) | Apache-2.0 | 2026-09-18 | Depth-aware procedural flares |
| [senyilmaz/ComfyUI-Reframe360](https://github.com/senyilmaz/ComfyUI-Reframe360) | MIT (in pyproject only) | 2026-07-16 | Real focal-length + sensor FOV maths and 4 lens projections (360° source only) |
| [quasiblob/ComfyUI-EsesImageLensEffects](https://github.com/quasiblob/ComfyUI-EsesImageLensEffects) | **Custom, personal use only, not OSI** | 2025-07 | Avoid |
| [vrgamegirl19/comfyui-vrgamedevgirl](https://github.com/vrgamegirl19/comfyui-vrgamedevgirl) | **Custom licence, not OSI** | 2026-10-16 | Fast film grain |
| [boobkake22/ComfyUI-FilmGrainLTXV](https://github.com/boobkake22/ComfyUI-FilmGrainLTXV) | Apache-2.0 | 2026-09 | Isolated copy of LTXVFilmGrain |
| [FLi79Za/comfyui_camsim2](https://github.com/FLi79Za/comfyui_camsim2) | MIT | 2026-02 | Camera sim (CA, noise, exposure) |
| [cubiq/ComfyUI_essentials](https://github.com/cubiq/ComfyUI_essentials) | MIT | 2025-04-14 | In maintenance only, and has no lens nodes |

There is no repo named "comfyui-lens-distortion".

### 3.4 Camera control for video generation
| Repo | Node licence | Model-weight caveat | Last push | Notes |
|---|---|---|---|---|
| ComfyUI core | GPL-3.0 | Wan2.1/2.2 Fun Control-Camera: Apache-2.0 | 2026-10-18 | `WanCameraEmbedding` (Plücker trajectory), `WanCameraImageToVideo`, track nodes, `CameraAngle`. Kling camera is a paid API node, so it is **not open** |
| [kijai/ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper) | Apache-2.0 | ReCamMaster, Uni3C, ATI: all Apache-2.0 | 2026-05-24 | ReCamMaster (re-shoot from new angles), Uni3C, FunCamera, ATI, WanMove |
| [aigc-apps/VideoX-Fun](https://github.com/aigc-apps/VideoX-Fun) | Apache-2.0 | Apache-2.0 | 2026-10-14 | Official Wan Fun Control-Camera nodes and the LingBot camera world model |
| [Lightricks/ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) | **LTX-2 Community License** (moved from Apache-2.0 on 2026-01-06) | Camera LoRAs: LTX-2 terms | 2026-10-14 | Loads the LTX camera LoRAs and IC-LoRAs |
| [MajoorWaldi/ComfyUI-Majoor-OmniCam](https://github.com/MajoorWaldi/ComfyUI-Majoor-OmniCam) | MIT | Depends on the target model | 2026-10-17 | Write a camera move once, compile it per model. Its HUD shows lens mm and FOV |
| [phazei/ComfyUI-Camera-Path](https://github.com/phazei/ComfyUI-Camera-Path) | Apache-2.0 | MoGe: MIT | 2026-09-25 | Reprojects MoGe geometry along a drawn path to make a guide video |
| [maosika-ai/ComfyUI-ReShot](https://github.com/maosika-ai/ComfyUI-ReShot) | Apache-2.0 | Video-depth licence unverified | 2026-09-13 | Copies a reference clip's camera move as depth, pose or canny |
| [arturitu/ComfyUI-scene-camera-action](https://github.com/arturitu/ComfyUI-scene-camera-action) | **No LICENSE file** (README badge says MIT) | — | 2026-09-03 | Three.js previz that outputs a guide video |
| [NyckM/3d-Camera-control-H3-Minimax](https://github.com/NyckM/3d-Camera-control-H3-Minimax) | Apache-2.0 | H3 licence unverified | 2026-09-20 | Turns a camera path into an H3 prompt |
| [jtydhr88/ComfyUI-qwenmultiangle](https://github.com/jtydhr88/ComfyUI-qwenmultiangle) | MIT | Apache-2.0 LoRA | 2026-09-13 | Image novel-view, not video |
| [chaojie/ComfyUI-CameraCtrl-Wrapper](https://github.com/chaojie/ComfyUI-CameraCtrl-Wrapper), [chaojie/ComfyUI-MotionCtrl](https://github.com/chaojie/ComfyUI-MotionCtrl) | Apache-2.0 | MIT / Apache-2.0 | 2024-06 (abandoned) | From the AnimateDiff/SVD era |

- **No ComfyUI node exists** for CamI2V, Hunyuan GameCraft or HY-WorldPlay.
- GameCraft's licence also excludes the EU, the UK and South Korea.

---

## 4. Has anyone published a lens/optics node pack?

**No integrated one exists.** The closest building blocks:

| Pack | Licence | ★ | What it covers | What's missing |
|---|---|---|---|---|
| [RealisticBokeh](https://github.com/marcsole96/ComfyUI-RealisticBokeh) | MIT | 1 | Physical CoC DOF (focal, f-stop, sensor, distance), blade/oval bokeh | No distortion, lens profiles, bodies, flares or prompt output |
| [Darkroom](https://github.com/jeremieLouvaert/ComfyUI-Darkroom) | MIT per README; no LICENSE file | 123 | 102 real **stills** lens profiles (distortion, CA, vignette) | No DOF, FOV maths, anamorphic or cine lenses |
| [NKD-VFX-Tools](https://github.com/Nekodificador/ComfyUI-NKD-VFX-Tools) | GPL-3.0 | 183 | Distortion, anamorphic squeeze, depth lens blur, fSpy solve | No focal/sensor model, no presets |
| [ER-VFX-Nodepack](https://github.com/esperandoelrender/ComfyUI-ER-VFX-Nodepack) | MIT | 6 | Lens and flare presets, including anamorphic | Not physically parameterised |
| [Optical-Realism](https://github.com/skatardude10/ComfyUI-Optical-Realism) | None | 30 | f-stop DOF preset, distortion, CA, halation | Not true CoC; no licence |

**Prompt-only camera/lens nodes** (text output, no optics):
- [kiko-flux2-prompt-builder](https://github.com/ComfyAssets/kiko-flux2-prompt-builder) (MIT, 65★)
- [ComfyUI-Cinematic-Prompt](https://github.com/yedp123/ComfyUI-Cinematic-Prompt) (MIT, 51★)
- [ComfyUI-AdvancedCameraPrompts](https://github.com/jandan520/ComfyUI-AdvancedCameraPrompts) (MIT, 36★)
- [ComfyUI-Prompt-Vault](https://github.com/jeremieLouvaert/ComfyUI-Prompt-Vault) (MIT, 5★)
- [comfyui-cinema-worldbuilder](https://github.com/Pro2004-a11/comfyui-cinema-worldbuilder) (MIT, 5★)
- "Cinematic Video Director (Multi-Shot & Optics)": registry only, created 2026-10-15, GitHub repo 404s, unverified ([registry](https://api.comfy.org/nodes/comfyui-director-prompt))

**Key evidence for the physical approach** [U]:
- The comfyui-cinema-worldbuilder README reports that on LTX-2.3, removing gear names from the prompt made **no visible difference**, based on a CLIP-embedding test.
- It also reports that "Arri / Master Primes" were not interpreted by the model.
- **Takeaway: lens names in prompts do little. Physically simulated optics is where the value is.**

**Open Higgsfield Cinema Studio clones (outside ComfyUI). All turn the picker into prompt modifiers sent to hosted models; none simulate optics:**
- [Anil-matcha/Open-Generative-AI](https://github.com/Anil-matcha/Open-Generative-AI) (MIT, ~30.7k★). Formerly "Open-Higgsfield-AI". 6 bodies, 11 lenses, 8–85mm, f/1.4–f/11.
- [NickPittas/DirectorsConsole](https://github.com/NickPittas/DirectorsConsole) (MIT, 361★). Renders through ComfyUI.
- [poptechstudio/ai-cinema-studio-engine](https://github.com/poptechstudio/ai-cinema-studio-engine) (MIT, 15★). 1,486 preset combinations.
- [VedSoni-dev/openfield](https://github.com/VedSoni-dev/openfield), [synthetic-ape/comfield](https://github.com/synthetic-ape/comfield) and [kevin9327/OpenSourceHiggsfield](https://github.com/kevin9327/OpenSourceHiggsfield). All MIT and all tiny; the last was created today, so **likely competitors**.
- [ClabstreamTeam/Open-Higgsfield-AI](https://github.com/ClabstreamTeam/Open-Higgsfield-AI) (no licence, 208★).

**What Higgsfield Cinema Studio offers:**
- **v4.0** (https://higgsfield.ai/blog/cinema-studio-4-0, 2026-08-12) [C]:
  - Camera: Auto, Modern, 35mm Film, 8mm Film, DV Camcorder.
  - Lens: Clean Sharp, Anamorphic, Vintage Anamorphic, Warm Vintage, Halation Vintage.
  - Aperture: f/1.4, f/4, f/11.
  - 30+ camera moves, plus genre, era, lighting, emotion wheel and palettes.
  - Up to 30 s, 1080p.
- **v3.5** (https://higgsfield.ai/blog/cinema-studio-3.5-full-tutorial) [C]: focal lengths 8/14/35/50/75mm.
- **Earlier versions named real gear** (RED V-Raptor, ARRI Alexa, Cooke S4, Panavision C-Series, Helios…) according to https://vidpros.com/higgsfield-cinema-studio/ [U].
- Product page: https://higgsfield.ai/cinema-studio
- In every version, the controls only condition generation. Nothing is simulated optically.

### The gap, and where Open Cinema fits
An open pack that would be new:
1. A shared **`CAMERA` / `LENS` data type**: body/sensor mm, focal length, T/f-stop, focus distance, anamorphic squeeze.
2. **Physical CoC depth of field** computed from that data, using depth from DA3-Small/Base or Video-Depth-Anything-Small (the commercially safe weights).
3. **Cine lens profiles**: distortion, CA, vignette, breathing, oval bokeh, streak flares.
4. **One picker** that drives the prompt, the camera path (LTX camera LoRA / Layout-To-Render, or Wan camera embedding) **and** the physical post-processing.

Licence hygiene for building it:
- Study RealisticBokeh (MIT) and Darkroom (no LICENSE file yet) freely, but only reuse code with a clear permissive licence.
- **Avoid deriving from** NKD (GPL), DepthFlow (AGPL), DepthCrafter (non-commercial) and no-licence packs, unless we choose a GPL-compatible licence on purpose.
- ComfyUI itself is GPL-3.0. Custom nodes are commonly shipped under MIT, Apache-2.0 or GPL; decide this early.

---

## Open questions to resolve next
- Does the LTX-2 Community License qualify for the **Open Weights Only** category? Ask in the Comfy Discord or at a Build Night.
- How exactly must the app use the Comfy Router/SDK? Read https://docs.comfy.org/development/api-development/sdks.
- Benchmark on our own 3090: LTX-2 19B plus a camera LoRA (GGUF), and LTX-2.5 Q5_K_M plus Layout-To-Render. Measure VRAM, time per clip and quality.
- Do the LTX-2 19B camera LoRAs actually work on 2.3 or 2.5?
- Judging criteria are unpublished. Assume the old ones (usefulness, completeness, reproducibility, delight) still apply.
