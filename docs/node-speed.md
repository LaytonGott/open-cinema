# Node speed

These numbers come from `npm run test:bench` on the RTX 3090 (NVIDIA GeForce RTX 3090, 24 GB). The benchmark tests rewrite this table. The `## Real clip` table is rewritten by `tests/test_bench_real.py` when run with `npm run test:bench`.

| node | frames | size | device | chunk_frames | seconds | peak GPU memory (GiB) |
| --- | --- | --- | --- | --- | --- | --- |
| OpenOptics_Anamorphic | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_ChromaticAberration | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_DepthOfField | 121 | 1280x704 | cuda | 8 | 2.7 | 0.64 |
| OpenOptics_DepthTemporalSmooth | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_DepthToMetric | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_FocalCrop | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_LensDistortion | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_Vignette | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |

## Limits

ComfyUI targets: Depth of Field 30 s, Temporal Smooth 10 s.

Standalone limits checked by `scripts/accept_real.py` and `tests/test_bench_real.py`: Depth of Field under 20 s, Temporal Smooth under 6 s, Depth to Metric under 10 s, peak GPU memory under 8 GiB.

## Real clip

Measured on the saved real clip (121 frames at 1280x704).

| measure | measured | standalone limit | ComfyUI target |
| --- | --- | --- | --- |
| Depth to Metric (s) | not yet measured | 10 | |
| Temporal Smooth (s) | not yet measured | 6 | 10 |
| Depth of Field (s) | not yet measured | 20 | 30 |
| Depth of Field layers (largest used) | not yet measured | | |
| Peak GPU memory (GiB) | not yet measured | 8 | |

## Compared with video generation

Depth of Field cost versus generating the clip (LTX-2 19B Q4_K_M, warm, 70.7 s per docs/benchmarks.md): Depth of Field takes 2.7 s for 121 frames, 3.8% of the 70.7 s to generate the clip (2.7 / 70.7).
