# Node speed

These numbers come from `npm run test:bench` on the RTX 3090 (NVIDIA GeForce RTX 3090, 24 GB). The benchmark tests rewrite this table.

| node | frames | size | device | chunk_frames | seconds | peak GPU memory (GiB) |
| --- | --- | --- | --- | --- | --- | --- |
| OpenOptics_Anamorphic | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_ChromaticAberration | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_DepthOfField | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_DepthTemporalSmooth | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_DepthToMetric | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_FocalCrop | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_LensDistortion | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |
| OpenOptics_Vignette | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |

## Compared with video generation

Depth of Field cost versus generating the clip (LTX-2 19B Q4_K_M, warm, 70.7 s per docs/benchmarks.md): not yet measured; npm run test:bench fills this in with the seconds and the percentage.
