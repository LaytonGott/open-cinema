"""Goal check: speed on real footage. Run with: node scripts/run-py.js scripts/accept_real.py

Uses the saved real clip (see manifest.json in the fixture folder): 121 frames of 1280x704, a Depth Anything depth video (8-bit,
near = bright) and the mask of the subject's red coat. The fixture folder is OPEN_OPTICS_FIXTURE_DIR, by default
D:\\OpenCinema\\fixtures\\real_clip. It runs the same chain as the end-to-end ComfyUI test, node by node, the way ComfyUI calls
them (CPU float32 tensors in and out):
    DepthToMetric (subject mode, mask, 2.0 m) -> DepthTemporalSmooth (0.7) -> DepthOfField (50 mm, f/1.8, focus 2.0 m, 24 px)
and checks: Depth of Field under 20 s, Temporal Smooth under 6 s, Depth to Metric under 10 s, GPU memory under 8 GiB, a cap on
the number of blur layers (the max_layers input), the torch Temporal Smooth against the stdlib reference, and one log record per
node call that says which device it really used. The limits here are tighter than the targets inside ComfyUI (30 s and 10 s) to leave room
for ComfyUI's own overhead (its cache, RAM pressure); the last check is a ComfyUI run. It needs the RTX 3090 and about 100 s
(VERIFY_NODE_TIMEOUT_MS=180000).
Prints one line per problem and exits 1 if there is any.
"""
import logging
import math
import os
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIXTURE = Path(os.environ.get("OPEN_OPTICS_FIXTURE_DIR", r"D:\OpenCinema\fixtures\real_clip"))
GIB = 1024 ** 3
LAYER_CAP_DEFAULT_MAX = 12

problems = []


def check(ok, message):
    if not ok:
        problems.append(message)


def finish():
    for p in problems:
        print(p)
    print("real footage speed: OK" if not problems else f"real footage speed: {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


try:
    import numpy as np
    import torch
    import open_optics_nodes as pack
    from open_optics.temporal import smooth_depth_sequence
except Exception as exc:
    print(f"cannot import numpy / torch / open_optics_nodes / open_optics.temporal: {exc}")
    sys.exit(1)

if not torch.cuda.is_available():
    print("CUDA is not available in this Python: cannot check the GPU requirement")
    sys.exit(1)
for name in ("frames_u8.npy", "depth_u8.npy", "subject_mask_u8.npy"):
    if not (FIXTURE / name).exists():
        print(f"the real-footage fixture is missing: {FIXTURE / name} (set OPEN_OPTICS_FIXTURE_DIR)")
        sys.exit(1)

# ---- capture the nodes' log records
records = []


class Collect(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())


logger = logging.getLogger("open_optics_nodes")
logger.setLevel(logging.INFO)
logger.addHandler(Collect())


def parse(message):
    return dict(re.findall(r"(\w+)=(\S+)", message))


def with_env(value, fn):
    old = os.environ.get("OPEN_OPTICS_DEVICE")
    os.environ["OPEN_OPTICS_DEVICE"] = value
    try:
        return fn()
    finally:
        if old is None:
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
        else:
            os.environ["OPEN_OPTICS_DEVICE"] = old


def call(key, **kw):
    cls = pack.NODE_CLASS_MAPPINGS[key]
    start = len(records)
    t = time.perf_counter()
    out = getattr(cls(), cls.FUNCTION)(**kw)
    torch.cuda.synchronize()
    return out, time.perf_counter() - t, records[start:]


# ---- 1. one log record per node call, naming the device that was really used (all eight nodes, small inputs, both devices)
torch.manual_seed(0)
IMG = torch.rand(3, 16, 24, 3, dtype=torch.float32)
RELATIVE = torch.rand(3, 16, 24, dtype=torch.float32)
METRES = RELATIVE * 4.0 + 1.0


def synth(key, name, spec):
    kind = spec[0]
    options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if isinstance(kind, (list, tuple)):
        return kind[0]
    data = RELATIVE if key == "OpenOptics_DepthToMetric" else METRES
    if kind == "IMAGE":
        return data.unsqueeze(-1).repeat(1, 1, 1, 3).contiguous() if "depth" in name.lower() else IMG.clone()
    if kind == "MASK":
        return data.clone()
    return options["default"] if "default" in options else {"FLOAT": 1.0, "INT": 1, "BOOLEAN": False, "STRING": ""}[kind]


def small_call(key):
    cls = pack.NODE_CLASS_MAPPINGS[key]
    types = cls.INPUT_TYPES()
    kwargs = {n: synth(key, n, s) for n, s in types.get("required", {}).items()}
    optional = types.get("optional", {}) or {}
    masks = [n for n, s in optional.items() if s[0] == "MASK" and "depth" in n.lower()]
    if masks:
        kwargs[masks[0]] = synth(key, masks[0], optional[masks[0]])
    start = len(records)
    getattr(cls(), cls.FUNCTION)(**kwargs)
    return records[start:]


for key in sorted(pack.NODE_CLASS_MAPPINGS):
    for requested, want in (("cuda", "cuda"), ("cpu", "cpu")):
        try:
            new = with_env(requested, lambda: small_call(key))
        except Exception as exc:
            problems.append(f"{key}: failed with OPEN_OPTICS_DEVICE={requested}: {type(exc).__name__}: {exc}")
            continue
        mine = [parse(m) for m in new if parse(m).get("node") == key]
        check(len(mine) == 1, f"{key}: expected exactly one log record 'node=... device=...' on logger open_optics_nodes per call, got {len(mine)} (all records: {new})")
        if len(mine) == 1:
            rec = mine[0]
            check(rec.get("device", "").startswith(want), f"{key}: OPEN_OPTICS_DEVICE={requested} but the log says device={rec.get('device')}")
            check("frames" in rec and "chunk_frames" in rec and "seconds" in rec, f"{key}: the log record must include frames=, chunk_frames= and seconds= ({new})")

# ---- 2. the torch Temporal Smooth against the stdlib reference
rng = random.Random(5)
N, H, W = 14, 6, 7
frames = []
for t in range(N):
    gain = 1.0 + 0.10 * math.sin(2.1 * t)
    frame = []
    for r in range(H):
        row = []
        for c in range(W):
            value = (2.0 if c < W // 2 else 6.0) * gain * (1.0 + rng.uniform(-0.05, 0.05))
            roll = rng.random()
            row.append(0.0 if roll < 0.04 else value * 3.0 if roll < 0.07 else value)
        frame.append(row)
    frames.append(frame)
frames[7][2][3] = float("nan")
reference = torch.tensor(smooth_depth_sequence(frames, strength=0.7), dtype=torch.float32)
node_out = with_env("cuda", lambda: call("OpenOptics_DepthTemporalSmooth", depth=torch.tensor(frames, dtype=torch.float32), strength=0.7)[0][0])
check(node_out.device.type == "cpu" and tuple(node_out.shape) == (N, H, W), f"Temporal Smooth must return a CPU tensor of shape {(N, H, W)}")
check(torch.allclose(node_out, reference, rtol=1e-4, atol=1e-4), f"the torch Temporal Smooth differs from open_optics.temporal.smooth_depth_sequence (the reference) by up to {float((node_out - reference).abs().max()):.5f} m")

# ---- 3. the real clip
os.environ["OPEN_OPTICS_DEVICE"] = "cuda"
frames_t = torch.from_numpy(np.load(FIXTURE / "frames_u8.npy")).float().div_(255.0).contiguous()
depth_rel = torch.from_numpy(np.load(FIXTURE / "depth_u8.npy")).float().div_(255.0).contiguous()
mask = torch.from_numpy(np.load(FIXTURE / "subject_mask_u8.npy")).float().div_(255.0).contiguous()
F = frames_t.shape[0]
print(f"fixture: {tuple(frames_t.shape)} frames, depth {tuple(depth_rel.shape)}, subject mask covers {float((mask > 0.5).float().mean()):.1%} of the pixels")

warm = call("OpenOptics_DepthOfField", image=frames_t[:2].clone(), depth_mask=(depth_rel[:2] * 5 + 1).clone(), focal_mm=50.0, f_number=1.8, focus_m=2.0, sensor_width_mm=36.0, quality="normal", max_radius_px=24, colorspace="srgb")  # CUDA warm-up
del warm
torch.cuda.reset_peak_memory_stats()

out, t_metric, rec = call("OpenOptics_DepthToMetric", depth_mask=depth_rel, subject_mask=mask, mode="subject", subject_m=2.0, anchor_scope="frame", inverse_depth=True, near_m=0.3, far_m=500.0)
metric = out[0]
print(f"Depth to Metric: {t_metric:.1f} s")
check(t_metric < 10.0, f"Depth to Metric took {t_metric:.1f} s on the real clip; it must take under 10 s")

out, t_smooth, rec = call("OpenOptics_DepthTemporalSmooth", depth=metric, strength=0.7)
smooth = out[0]
print(f"Temporal Smooth: {t_smooth:.1f} s")
check(t_smooth < 6.0, f"Temporal Smooth took {t_smooth:.1f} s on the real clip; it must take under 6 s here (10 s in ComfyUI)")
check(smooth.device.type == "cpu" and smooth.shape == metric.shape and bool(torch.isfinite(smooth).all()), "Temporal Smooth must return a finite CPU tensor of the input's shape")
smooth_log = [parse(m) for m in rec if parse(m).get("node") == "OpenOptics_DepthTemporalSmooth"]
check(len(smooth_log) == 1 and smooth_log[0].get("device", "").startswith("cuda"), f"Temporal Smooth with OPEN_OPTICS_DEVICE=cuda must run on the GPU and say so in its log; log: {rec}")

settings = dict(focal_mm=50.0, f_number=1.8, focus_m=2.0, sensor_width_mm=36.0, quality="normal", max_radius_px=24, colorspace="srgb")
torch.cuda.reset_peak_memory_stats()
out, t_dof, rec = call("OpenOptics_DepthOfField", image=frames_t, depth_mask=smooth, **settings)
peak = torch.cuda.max_memory_allocated() / GIB
result, coc = out[0], out[1]
print(f"Depth of Field: {t_dof:.1f} s, peak GPU memory {peak:.2f} GiB")
check(t_dof < 20.0, f"Depth of Field took {t_dof:.1f} s on the real clip ({F} frames at 1280x704); it must take under 20 s here (30 s in ComfyUI)")
check(peak < 8.0, f"Depth of Field used {peak:.2f} GiB of GPU memory; it must stay under 8 GiB")
check(tuple(result.shape) == tuple(frames_t.shape) and result.dtype == torch.float32 and result.device.type == "cpu" and bool(torch.isfinite(result).all())
      and float(result.min()) >= -1e-5 and float(result.max()) <= 1.0 + 1e-5, "Depth of Field must return a finite CPU float32 image of the input's shape within 0..1")
dof_log = [parse(m) for m in rec if parse(m).get("node") == "OpenOptics_DepthOfField"]
check(len(dof_log) == 1, f"Depth of Field must log exactly one record per call; got {rec}")
default_layers_seen = None
if len(dof_log) == 1:
    check(dof_log[0].get("device", "").startswith("cuda"), f"Depth of Field log says device={dof_log[0].get('device')}, expected cuda")
    check("layers" in dof_log[0], "the Depth of Field log record must include layers=<the largest number of blur layers used in any chunk>")
    if "layers" in dof_log[0]:
        default_layers_seen = int(dof_log[0]["layers"])
        check(default_layers_seen <= LAYER_CAP_DEFAULT_MAX, f"Depth of Field used {default_layers_seen} blur layers with the default max_layers; the default cap must be at most {LAYER_CAP_DEFAULT_MAX}")

# the picture must still be right: sharp where the blur radius is under 0.2 px, visibly blurred where it is over 4 px
radius = coc * 24.0
sharp, blurred = radius < 0.2, radius > 4.0
check(bool(sharp.any()) and bool(blurred.any()), "the real clip must have both in-focus and strongly out-of-focus pixels in the circle-of-confusion output")
if bool(sharp.any()) and bool(blurred.any()):
    diff = (result - frames_t).abs().mean(dim=-1)
    sharp_change, blur_change = float(diff[sharp].mean()), float(diff[blurred].mean())
    print(f"mean change: in-focus pixels {sharp_change:.4f}, blurred pixels {blur_change:.4f}")
    check(sharp_change < 0.01, f"in-focus pixels changed by {sharp_change:.4f} on average; they must stay within 0.01")
    check(blur_change > 0.02, f"out-of-focus pixels changed by only {blur_change:.4f} on average; the blur must show (above 0.02)")

# ---- 4. the layer cap
types = pack.NODE_CLASS_MAPPINGS["OpenOptics_DepthOfField"].INPUT_TYPES()
spec = {**types.get("required", {}), **(types.get("optional") or {})}.get("max_layers")
check(spec is not None and spec[0] == "INT", "Depth of Field has no max_layers INT input")
check("max_layers" not in types.get("required", {}), "max_layers was added after the first release, so it must be optional (in INPUT_TYPES 'optional') with a default")
if spec is not None and spec[0] == "INT":
    check(isinstance(spec[1], dict) and 1 <= spec[1].get("default", 0) <= LAYER_CAP_DEFAULT_MAX and spec[1].get("min", 0) == 1, f"max_layers needs min 1 and a default of at most {LAYER_CAP_DEFAULT_MAX}; got {spec[1:]}")
    sl = slice(40, 56)
    base = dict(image=frames_t[sl].clone(), depth_mask=smooth[sl].clone(), **settings)
    full, _, rec_full = call("OpenOptics_DepthOfField", **base)
    capped, _, rec_cap = call("OpenOptics_DepthOfField", max_layers=3, **base)
    layers_cap = [int(parse(m)["layers"]) for m in rec_cap if parse(m).get("node") == "OpenOptics_DepthOfField" and "layers" in parse(m)]
    layers_full = [int(parse(m)["layers"]) for m in rec_full if parse(m).get("node") == "OpenOptics_DepthOfField" and "layers" in parse(m)]
    check(bool(layers_cap) and max(layers_cap) <= 3, f"with max_layers=3 the log must show at most 3 layers; got {layers_cap}")
    check(bool(layers_full) and bool(layers_cap) and max(layers_cap) <= max(layers_full), f"a lower cap must not use more layers than the default ({layers_cap} vs {layers_full})")
    step = float((capped[0] - full[0]).abs().mean())
    check(step < 0.03, f"max_layers=3 changes the picture by {step:.4f} on average against the default; capping the layers must not wreck the blur (limit 0.03)")
    d3 = (capped[0] - frames_t[sl]).abs().mean(dim=-1)
    r3 = capped[1] * 24.0
    check(float(d3[r3 > 4.0].mean()) > 0.02, "with max_layers=3 the out-of-focus pixels are no longer visibly blurred")

finish()
