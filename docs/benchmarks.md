# LTX benchmarks: RTX 3090 (24 GB) with 32 GB RAM

Run on 2026-10-17. Each run makes one ~5-second clip at 720p-class resolution, text-to-video, with the same prompt for both models. Raw numbers are in [`bench/results/*.json`](../bench/results/), and the harness is in [`bench/`](../bench/).

## TL;DR

| | LTX-Video 0.9.8 13B distilled (fp8 weights) | LTX-2 19B distilled, **Q4_K_M GGUF** |
|---|---|---|
| **Cold run** (fresh ComfyUI process) | **77 s** | **199 s** (text encoding on CPU takes about 95 s of this) |
| **Warm run** (models loaded, new seed) | **63 s** | **70 s** |
| Sampling speed | 8 steps × 6.8 s/it at 1280×704 | 8 steps × 3.6 s/it at 640×352, then 3 refine steps × 9.7 s/it at 1280×704 |
| **Peak VRAM** (whole GPU / above baseline) | 23.6 GB / **21.7 GB** | 21.6 GB / **20.3 GB** |
| **Peak RAM, ComfyUI process** (working set) | **4.9 GB** | **13.0 GB** |
| **Peak system RAM used** (baseline → peak, of 31.75 GB) | 21.7 → **26.1 GB** | 22.1 → **31.7 GB (RAM exhausted, ~2 GB paged out)** |
| Output | 1280×704, 121 frames, 24 fps, 5.04 s, no audio | 1280×704, 121 frames, 24 fps, 5.04 s, **plus an AAC audio track** |
| Quality, short version | Clean and sharp, but a glossy "AI" look; weak prompt adherence on one of the two seeds | More filmic and natural, with better motion and cinematography; pseudo-text on paper |

**Bottom line:**
- Both run on this 3090.
- **LTX-2 Q4_K_M is the better generator** and is as fast as 0.9.8 once warm.
- Its cost is RAM. Offloading the Gemma 3 12B encoder to the CPU fills the 32 GB of system RAM while your normal apps are open.
  - Mitigations are under [Recommendations](#recommendations).

---

## Setup

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 3090, 24 GB, driver 610.88. About 1.3–1.9 GB was already used by other apps before each run. |
| System RAM | 31.75 GB. **21.7–22.6 GB was already in use by your other apps at the start of each run.** None of your apps were closed (as you asked), so ComfyUI had about 9–10 GB to work with. |
| Disk | Models on D: (Samsung 970 NVMe) |
| ComfyUI | Official Windows portable **v0.41.0** (commit `98cc0bf`), embedded Python 3.13.14, torch 2.14.0+cu130. SHA-256 matched the GitHub release digest. Installed at `D:\OpenCinema\ComfyUI_windows_portable`. |
| Custom nodes | [city96/ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) `6ea2651` (Apache-2.0), used only for the GGUF loader |
| Comfy SDK | `comfy-sdk` 0.5.0 + `comfy-api-proxy` 0.1.6, both in the project `.venv`. All runs were submitted **through the SDK**: SDK → proxy on :8189 → ComfyUI on :8188. |
| Launch flags | Defaults (`--windows-standalone-build`). No `--lowvram` or `--reserve-vram`. |

### Model files
Every file's SHA-256 was checked against the Hugging Face LFS hash.

| Model | File | Size | Source |
|---|---|---|---|
| LTX 0.9.8 13B | `ltxv-13b-0.9.8-distilled-fp8.safetensors` | 15.7 GB | [Lightricks/LTX-Video](https://huggingface.co/Lightricks/LTX-Video) |
| 0.9.8 text encoder | `t5xxl_fp16.safetensors` | 9.8 GB | [comfyanonymous/flux_text_encoders](https://huggingface.co/comfyanonymous/flux_text_encoders) |
| LTX-2 19B | `ltx-2-19b-distilled_Q4_K_M.gguf` | 12.65 GB | [Kijai/LTXV2_comfy](https://huggingface.co/Kijai/LTXV2_comfy) |
| LTX-2 text encoder | `gemma_3_12B_it_fp8_scaled.safetensors` | 13.2 GB | [Comfy-Org/ltx-2](https://huggingface.co/Comfy-Org/ltx-2) |
| LTX-2 text connector | `ltx-2-19b-embeddings_connector_distill_bf16.safetensors` | 2.9 GB | Kijai/LTXV2_comfy |
| LTX-2 VAEs | `LTX2_video_vae_bf16` 2.4 GB, `LTX2_audio_vae_bf16` 0.2 GB | | Kijai/LTXV2_comfy |
| LTX-2 upscaler | `ltx-2-spatial-upscaler-x2-1.0.safetensors` | 1.0 GB | [Lightricks/LTX-2](https://huggingface.co/Lightricks/LTX-2) |

Both models are under Lightricks licences: Open-Weights for 0.9.8, and the LTX-2 Community License for LTX-2. See research.md §2.

## Method
- **Prompt (both models):** a slow dolly-in on a woman reading a handwritten letter by a rainy night window, with a tungsten lamp and city bokeh. Full text is in [`bench/workflows.py`](../bench/workflows.py).
- **Resolution:** 1280×704. LTX latents need dimensions divisible by 32, so 720 becomes 704; ComfyUI's own LTX-2 template does the same.
- **Length:** 121 frames at 24 fps = 5.04 s.
- **Graphs** follow ComfyUI's bundled templates:
  - **0.9.8** follows `ltxv_text_to_video`, run as a **single pass at full resolution**. Distilled sigmas, 8 steps, CFG 1, euler. Text encoder on GPU (default).
  - **LTX-2** follows `video_ltx2_t2v_distilled`, the official **two-stage** pipeline:
    1. 8 distilled steps at 640×352.
    2. A ×2 latent upscale.
    3. 3 refine steps at 1280×704, using euler_ancestral and CFG 1.
  - LTX-2 generates audio and video jointly.
  - **Text encoder on CPU** (`LTXAVTextEncoderLoader device=cpu`). Q4_K_M (12.65 GB) plus Gemma fp8 (13.2 GB) is 25.9 GB, more than the ~22 GB of free VRAM. So, per your instruction, **only the encoder was offloaded**, and the diffusion model loaded fully into VRAM ("loaded completely … 14945 MB, full load: True").
  - Both use `VAEDecodeTiled` (512 / 64 / 4096 / 8), as in the templates.
- **Cold run:** ComfyUI restarted fresh, seed 42. The OS file cache was *not* flushed; with only about 10 GB of RAM free, little of the model files could stay cached anyway.
- **Warm run:** same process, models already loaded, seed 43. The text conditioning is cached because the prompt is unchanged, so a warm run is sampling plus decode.
- **Timing:** wall-clock time from SDK submit to completion. ComfyUI's own "Prompt executed in" figure is shown alongside.
- **Memory:** sampled every 0.5 s.
  - **VRAM** comes from NVML and covers the whole GPU. It is reported both as a total and above the pre-run baseline (other apps' usage).
  - **ComfyUI RAM** is the process working set, i.e. resident memory.
  - **System RAM** is total minus available.
  - **Pagefile** is the Windows pagefile usage.

## Results

### Time
| Run | Wall (s) | ComfyUI reported (s) | Phases |
|---|---|---|---|
| 0.9.8 13B, cold | 80.5 | 77.1 | Load ~10 s, then sampling 8 × ~6.8 s/it (51 s), then tiled VAE decode |
| 0.9.8 13B, warm | 65.6 | 63.4 | Sampling 8 × 6.8 s/it (54 s), then decode |
| LTX-2 Q4, cold | 200.7 | 199.5 | **Gemma load + CPU encode ≈ 96 s** (the GPU stays idle until t = 96 s), then GGUF load, stage 1 (8 × 3.8 s/it = 30 s), upscale, stage 2 (3 × 9.7 s/it = 29 s), video + audio decode |
| LTX-2 Q4, warm | 70.7 | 70.5 | Stage 1 (8 × 3.7 s/it = 29 s), stage 2 (3 × 9.7 s/it = 29 s), decode |

### Memory: what each run actually used
| Run | VRAM peak, whole GPU | VRAM above baseline | ComfyUI working set peak | ComfyUI private commit peak¹ | System RAM used (baseline → peak) | Min. RAM available | Pagefile (baseline → peak) |
|---|---|---|---|---|---|---|---|
| 0.9.8 13B, cold | 23.57 GB | 21.69 GB | 4.90 GB | 29.2 GB | 21.65 → 26.14 GB | 5.6 GB | 2.37 → 2.34 GB |
| 0.9.8 13B, warm | 21.72 GB | 3.84 GB² | 4.92 GB | 27.8 GB | 25.01 → 25.82 GB | 5.9 GB | 2.30 → 2.30 GB |
| LTX-2 Q4, cold | 21.57 GB | 20.29 GB | **12.99 GB** | 28.6 GB | 22.10 → **31.74 GB** | **0.0 GB** | 2.30 → **4.35 GB** |
| LTX-2 Q4, warm | 20.73 GB | 3.94 GB² | 12.99 GB | 28.8 GB | 22.61 → 24.07 GB | 7.7 GB | 3.83 → 3.83 GB |

¹ **Private commit is the address space ComfyUI reserved, not RAM it used.** ComfyUI 0.41's "dynamic VRAM loading" stages whole models in reserved memory. That reservation counts against the Windows commit limit (RAM + pagefile), but most of it never becomes resident. Working set is the column that reflects physical RAM.

² In warm runs the models were already resident from the cold run, so the baseline already contains them (16.8–17.9 GB). Read the whole-GPU peak instead.

**What this means:**
- **LTX 0.9.8 13B is the lighter model on RAM.**
  - T5-XXL and the fp8 13B weights both stream to the GPU.
  - ComfyUI stays under 5 GB resident.
  - VRAM gets close to full (23.6 of 24 GB). The log shows no partial-load or offload messages.
- **LTX-2 Q4_K_M fits in VRAM comfortably**: the diffusion model loaded fully, with a 21.6 GB peak. RAM is the bottleneck, not VRAM.
  - The CPU-offloaded Gemma 3 12B takes **15.3 GB of RAM** ("LTXAVTEModel_ loaded completely; 15309 MB" on CPU).
  - Together with your ~22 GB of apps, **available RAM hit zero at points during a ~40 s window** (t = 47–85 s), and Windows paged roughly 2 GB to the pagefile.
  - Nothing crashed, but your other apps may have felt sluggish during that window.
  - The warm run reuses the cached conditioning and stays well within limits.

### Quality notes
Each strip shows frames 0, 60 and 120.

**LTX-Video 0.9.8 13B**, seed 42 (cold) and seed 43 (warm):

![0.9.8 cold](benchmarks/ltxv098-13b-cold_sheet.jpg)
![0.9.8 warm](benchmarks/ltxv098-13b-warm_sheet.jpg)

- **Good:**
  - The scene is coherent, and the lighting matches the prompt: warm lamp, blue rainy window, round bokeh, drops on the glass.
  - No flicker or morphing across the 121 frames.
  - Seed 43 shows legible-looking handwriting and a real camera reframe.
- **Weak:**
  - **Prompt adherence varies with the seed.** Seed 42 drew a subject who reads as male, in a blazer, holding a pen, and **the dolly-in barely moves**: the three frames are almost identical.
  - The image has a glossy, over-saturated, "plastic skin" HDR look.
  - The depth of field is shallow on seed 42 but nearly deep on seed 43, even though the prompt is identical.
  - No audio.

**LTX-2 19B Q4_K_M**, seed 42 (cold) and seed 43 (warm):

![LTX-2 cold](benchmarks/ltx2-19b-q4-cold_sheet.jpg)
![LTX-2 warm](benchmarks/ltx2-19b-q4-warm_sheet.jpg)

- **Good:**
  - Clearly the more cinematic of the two: a natural, film-like grade, realistic skin, and convincing rain-streaked glass with large defocused city lights.
  - Seed 43 has strong camera language: it starts on the hands and letter, tilts up and pushes in to a profile, and the lamp reflects in the window.
  - Motion is smooth across all 121 frames.
  - An audio track was generated (AAC, 24 kHz). **I have not listened to it**, so its quality is unevaluated.
- **Weak:**
  - The **letter shows nonsense pseudo-text** ("K€tkbtp…"), which is prominent on seed 42.
  - Seed 42 framed the woman frontally, not over a desk, and the push-in is subtle.
  - Fine detail is slightly softer than 0.9.8, because the two-stage pipeline renders at 640×352 and then upscales.
  - Q4 quantization artifacts are not obvious at this viewing size. No higher-precision LTX-2 reference was run, so the Q4 quality loss is **unmeasured**.
- **For Open Optics:** neither model gives controllable, physically consistent depth of field. The bokeh amount changes with the seed. That supports doing DoF in post (see [spec.md](spec.md)).

## Caveats
- **One seed per run.** These are single samples, not statistics. Quality varies a lot by seed, as seeds 42 and 43 show.
- **The pipelines are not identical.** 0.9.8 is a single full-resolution pass; LTX-2 is the official two-stage pipeline. Each is the recommended ComfyUI template for its model, which is the fairer real-world comparison, but it is not a like-for-like compute comparison.
- **The baseline was a busy machine**, with about 22 GB of RAM in use by your apps. On a clean machine, the LTX-2 cold run would not page, and its CPU encode would probably be faster.
- **The CPU text-encode time (~95 s) includes reading 13.2 GB from disk** under memory pressure. It is paid only when the prompt changes.
- **Not tested:** LTX-2 with the text encoder on the GPU. ComfyUI would swap Gemma in and out of VRAM, which needs the same ~13–15 GB of RAM to hold it when it is offloaded.

## Recommendations
1. **Use LTX-2 19B Q4_K_M as the main generator** on this machine. It has better quality and audio, and is as fast as 0.9.8 when warm (70 s vs 63 s per 5-s clip).
2. **Cut RAM pressure from the encoder.** Options, best first:
   - (a) Try `gemma_3_12B_it_fp4_mixed.safetensors` (9.45 GB, also in Comfy-Org/ltx-2). This is untested; benchmark it next.
   - (b) Encode each prompt once and reuse the conditioning. The Open Cinema app can cache conditioning per shot.
   - (c) Close heavy apps during cold runs.
3. **Treat 0.9.8 13B as the fallback.** It is light on RAM, but has weaker prompt adherence and no audio. Keep it for depth/pose IC-LoRA experiments (research.md §2).

## Reproduce

Start ComfyUI and the proxy:

```bash
D:/OpenCinema/ComfyUI_windows_portable/python_embeded/python.exe -s D:/OpenCinema/ComfyUI_windows_portable/ComfyUI/main.py --windows-standalone-build --disable-auto-launch --port 8188
```

```bash
.venv/Scripts/comfy-api-proxy.exe run --comfyui http://127.0.0.1:8188 --port 8189
```

Then, from the `bench/` folder:

```bash
COMFY_BASE_URL=http://127.0.0.1:8189 ../.venv/Scripts/python.exe run_bench.py ltxv-0.9.8-13b --seed 42 --label ltxv098-13b-cold --comfy-log D:/OpenCinema/logs/comfyui.log
```

```bash
COMFY_BASE_URL=http://127.0.0.1:8189 ../.venv/Scripts/python.exe run_bench.py ltx2-19b-q4 --seed 42 --encoder-device cpu --label ltx2-19b-q4-cold --comfy-log D:/OpenCinema/logs/comfyui.log
```
