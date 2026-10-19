"""Goal check: GPU speed. Run with: node scripts/run-py.js scripts/accept_gpu.py

Needs the RTX 3090 (CUDA must be available) and about 45 s; the loop is started with VERIFY_NODE_TIMEOUT_MS=180000 so that
a node check may run that long. Checks:
  1. open_optics_nodes.device.get_device() exists, honours OPEN_OPTICS_DEVICE (cpu, cuda, auto), rejects other values.
  2. Every registered node gives the same result (atol 1e-4) on the CPU and on the GPU, and the GPU run really used the GPU.
  3. Every node has a chunk_frames input, and chunk_frames=1 and a larger chunk give the same result.
  4. Depth of Field on 121 synthetic frames of 1280x704: under 30 s from the node call to the returned CPU tensor, peak GPU
     memory under 8 GiB, output float32 [121, 704, 1280, 3] in 0..1.
Prints one line per problem and exits 1 if there is any.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

problems = []


def check(ok, message):
    if not ok:
        problems.append(message)


def finish():
    for p in problems:
        print(p)
    print("gpu speed: OK" if not problems else f"gpu speed: {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


try:
    import torch
    import open_optics_nodes as pack
    from open_optics_nodes import device as device_module
except Exception as exc:
    print(f"cannot import torch / open_optics_nodes / open_optics_nodes.device: {exc}")
    sys.exit(1)

if not torch.cuda.is_available():
    print("CUDA is not available in this Python (it needs the CUDA build of torch and the GPU free): cannot check the GPU requirement")
    sys.exit(1)

GIB = 1024 ** 3


def with_device(value, fn):
    old = os.environ.get("OPEN_OPTICS_DEVICE")
    if value is None:
        os.environ.pop("OPEN_OPTICS_DEVICE", None)
    else:
        os.environ["OPEN_OPTICS_DEVICE"] = value
    try:
        return fn()
    finally:
        if old is None:
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
        else:
            os.environ["OPEN_OPTICS_DEVICE"] = old


# 1. the device helper
check(with_device("cpu", device_module.get_device).type == "cpu", "OPEN_OPTICS_DEVICE=cpu must give the CPU")
check(with_device("cuda", device_module.get_device).type == "cuda", "OPEN_OPTICS_DEVICE=cuda must give the GPU")
check(with_device("auto", device_module.get_device).type == "cuda", "OPEN_OPTICS_DEVICE=auto must give the GPU when CUDA is available and ComfyUI is not loaded")
check(with_device(None, device_module.get_device).type == "cuda", "with OPEN_OPTICS_DEVICE unset the device must be the GPU when CUDA is available")
try:
    with_device("tpu", device_module.get_device)
    problems.append("OPEN_OPTICS_DEVICE=tpu must raise ValueError")
except ValueError:
    pass

# 2 and 3. every node on both devices, and chunk invariance
torch.manual_seed(0)
FRAMES = 5
IMAGE = torch.rand(FRAMES, 16, 16, 3, dtype=torch.float32)
METRES = torch.rand(FRAMES, 16, 16, dtype=torch.float32) * 4.0 + 1.0
RELATIVE = torch.rand(FRAMES, 16, 16, dtype=torch.float32)


def depth_data(key):
    return RELATIVE if key in ("OpenOptics_DepthToMetric",) else METRES


def synth(key, name, spec):
    kind = spec[0]
    options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if isinstance(kind, (list, tuple)):
        return kind[0]
    if kind == "IMAGE":
        return depth_data(key).unsqueeze(-1).repeat(1, 1, 1, 3).contiguous() if "depth" in name.lower() else IMAGE.clone()
    if kind == "MASK":
        return depth_data(key).clone()
    if kind in ("FLOAT", "INT", "BOOLEAN", "STRING"):
        return options["default"] if "default" in options else {"FLOAT": 1.0, "INT": 1, "BOOLEAN": False, "STRING": ""}[kind]
    raise ValueError(f"cannot synthesise {kind} for {name}")


def run(key, cls, **extra):
    inputs = cls.INPUT_TYPES()
    kwargs = {name: synth(key, name, spec) for name, spec in inputs.get("required", {}).items()}
    optional = inputs.get("optional", {}) or {}
    depth_masks = [n for n, s in optional.items() if s[0] == "MASK" and "depth" in n.lower()]
    if depth_masks:  # a node that offers depth as a MASK or an IMAGE: connect the MASK
        kwargs[depth_masks[0]] = synth(key, depth_masks[0], optional[depth_masks[0]])
    kwargs.update(extra)
    return getattr(cls(), cls.FUNCTION)(**kwargs)


def same(a, b, atol):
    return (isinstance(a, tuple) and isinstance(b, tuple) and len(a) == len(b)
            and all(torch.allclose(x.float().cpu(), y.float().cpu(), atol=atol, rtol=0) for x, y in zip(a, b)
                    if isinstance(x, torch.Tensor) and isinstance(y, torch.Tensor)))


for key, cls in sorted(pack.NODE_CLASS_MAPPINGS.items()):
    try:
        on_cpu = with_device("cpu", lambda: run(key, cls))
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        before = torch.cuda.memory_allocated()
        on_gpu = with_device("cuda", lambda: run(key, cls))
        used = torch.cuda.max_memory_allocated()
        check(same(on_cpu, on_gpu, 1e-4), f"{key}: the result on the GPU differs from the result on the CPU by more than 1e-4")
        check(used > before, f"{key}: running with OPEN_OPTICS_DEVICE=cuda did not use the GPU (no CUDA memory was allocated)")
        for out in on_gpu:
            if isinstance(out, torch.Tensor):
                check(out.device.type == "cpu", f"{key}: outputs must be returned on the CPU (ComfyUI passes tensors between nodes on the CPU)")
        accepted = cls.INPUT_TYPES().get("required", {}).get("chunk_frames") or cls.INPUT_TYPES().get("optional", {}).get("chunk_frames")
        check(accepted is not None and accepted[0] == "INT", f"{key}: no chunk_frames INT input")
        if accepted is not None:
            one = with_device("cuda", lambda: run(key, cls, chunk_frames=1))
            many = with_device("cuda", lambda: run(key, cls, chunk_frames=FRAMES))
            check(same(one, many, 1e-5), f"{key}: chunk_frames=1 and chunk_frames={FRAMES} give different results (differences above 1e-5)")
    except Exception as exc:
        problems.append(f"{key}: failed on both devices or with chunks: {type(exc).__name__}: {exc}")

# 4. the Depth of Field benchmark on real-size synthetic frames
F, H, W = 121, 704, 1280
gen = torch.Generator().manual_seed(1)
yy = torch.linspace(0, 1, H).view(1, H, 1, 1)
xx = torch.linspace(0, 1, W).view(1, 1, W, 1)
phase = torch.linspace(0, 1, F).view(F, 1, 1, 1)
image = (0.25 + 0.5 * (0.5 + 0.5 * torch.sin(12.0 * xx + 3.0 * yy + 2.0 * phase)) + 0.1 * torch.rand(F, H, W, 3, generator=gen)).clamp(0, 1).float().contiguous()
depth = (1.0 + 9.0 * yy.view(1, H, 1) + torch.zeros(F, 1, W)).float().contiguous()  # a ground plane from 1 m (top) to 10 m (bottom)
depth[:, 200:500, 400:700] = 3.0  # a subject at the focus distance
depth[:, 100:300, 900:1100] = 1.2  # a foreground object
cls = pack.NODE_CLASS_MAPPINGS.get("OpenOptics_DepthOfField")
if cls is None:
    problems.append("OpenOptics_DepthOfField is not registered")
else:
    os.environ["OPEN_OPTICS_DEVICE"] = "cuda"
    try:
        node = cls()
        settings = dict(focal_mm=50.0, f_number=2.0, focus_m=3.0, sensor_width_mm=36.0, quality="normal", max_radius_px=32, colorspace="srgb")
        call = getattr(node, cls.FUNCTION)
        warm = call(image=image[:2].clone(), depth_mask=depth[:2].clone(), **settings)  # CUDA and kernel start-up, not timed
        del warm
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        out = call(image=image, depth_mask=depth, **settings)
        torch.cuda.synchronize()
        seconds = time.perf_counter() - start
        peak = torch.cuda.max_memory_allocated() / GIB
        print(f"Depth of Field, {F} frames at {W}x{H}: {seconds:.1f} s, peak GPU memory {peak:.2f} GiB")
        check(seconds < 30.0, f"Depth of Field took {seconds:.1f} s for {F} frames at {W}x{H}; it must take under 30 s")
        check(peak < 8.0, f"Depth of Field used {peak:.2f} GiB of GPU memory at its peak; it must stay under 8 GiB (process the frames in chunks)")
        result = out[0]
        check(tuple(result.shape) == (F, H, W, 3) and result.dtype == torch.float32 and result.device.type == "cpu",
              f"Depth of Field output must be a CPU float32 tensor of shape {(F, H, W, 3)}; got {tuple(result.shape)} {result.dtype} on {result.device}")
        check(bool(torch.isfinite(result).all()) and float(result.min()) >= -1e-5 and float(result.max()) <= 1.0 + 1e-5, "Depth of Field output is not finite or not within 0..1")
        check(float((result - image).abs().mean()) > 0.003, "Depth of Field barely changed the image: the benchmark scene has out-of-focus areas, so the blur must show")
    except Exception as exc:
        problems.append(f"the Depth of Field benchmark failed: {type(exc).__name__}: {exc}")

for path in sorted((ROOT / "open_optics_nodes").glob("*.py")):
    if path.name == "device.py":
        continue
    text = path.read_text(encoding="utf-8")
    check(".cuda(" not in text and 'device="cuda"' not in text and "device='cuda'" not in text and 'torch.device("cuda")' not in text,
          f"{path.name} hard-codes the GPU; use open_optics_nodes.device.get_device()")

finish()
