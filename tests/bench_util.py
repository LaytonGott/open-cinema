"""Helpers for benchmark tests: node kwargs, timing and peak GPU memory."""

import os
import time
from unittest import mock

import torch

BENCH_FRAMES = 121
BENCH_HEIGHT = 704
BENCH_WIDTH = 1280

_FRAME_KEYS = ("image", "depth", "depth_mask")


def _defaults(cls):
    out = {}
    for name, spec in cls.INPUT_TYPES()["required"].items():
        if spec[0] in ("IMAGE", "MASK"):
            continue
        if isinstance(spec[0], list):
            out[name] = spec[0][0]
        else:
            out[name] = spec[1]["default"]
    return out


def node_kwargs(cls, image, depth):
    """Build the keyword arguments for calling a node class's function.

    Every required input that is not IMAGE or MASK gets its default (the
    first item for choice inputs). image is a float32 tensor
    [frames, height, width, 3] in 0 to 1; depth is a tensor
    [frames, height, width] in metres. image is set if the node requires
    it, depth if it requires depth, and depth_mask (given depth) if it
    has an optional depth_mask input.

    Returns a dict of keyword arguments.
    """
    kwargs = _defaults(cls)
    types = cls.INPUT_TYPES()
    if "image" in types["required"]:
        kwargs["image"] = image
    if "depth" in types["required"]:
        kwargs["depth"] = depth
    if "depth_mask" in types.get("optional", {}):
        kwargs["depth_mask"] = depth
    return kwargs


def run_bench(cls, kwargs, chunk_frames=None):
    """Run a node on the GPU and measure wall time and peak GPU memory.

    Sets OPEN_OPTICS_DEVICE=cuda for the call. First runs an untimed
    warm-up on the first 2 frames of the image, depth and depth_mask
    inputs, then resets the memory statistics and times the real call.
    chunk_frames (frames) is passed to the node only when not None.

    Returns (outputs, seconds, peak_gib): the node's return value, the
    elapsed time in seconds and the peak allocated GPU memory in GiB.
    """
    kwargs = dict(kwargs)
    if chunk_frames is not None:
        kwargs["chunk_frames"] = chunk_frames
    node = cls()
    func = getattr(node, cls.FUNCTION)
    warm = {k: (v[:2] if k in _FRAME_KEYS else v) for k, v in kwargs.items()}
    with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cuda"}):
        func(**warm)
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        outputs = func(**kwargs)
        torch.cuda.synchronize()
        seconds = time.perf_counter() - start
        peak_gib = torch.cuda.max_memory_allocated() / 1024 ** 3
    return outputs, seconds, peak_gib


def record_result(node_key, chunk_frames, seconds, peak_gib, path=None):
    """Write a benchmark result into the node speed table.

    Rewrites the line starting with "| <node_key> |" in docs/node-speed.md
    (or in path) with chunk_frames (frames), seconds (1 decimal) and
    peak_gib (GiB, 2 decimals); every other line is left untouched, and
    nothing changes if the row is missing. Only benchmark tests may call it.

    Returns None.
    """
    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "node-speed.md")
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = f.read().splitlines(keepends=True)
    prefix = f"| {node_key} |"
    changed = False
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            ending = line[len(line.rstrip("\r\n")):]
            lines[i] = (f"| {node_key} | {BENCH_FRAMES} | {BENCH_WIDTH}x{BENCH_HEIGHT}"
                        f" | cuda | {chunk_frames} | {seconds:.1f} | {peak_gib:.2f} |"
                        f"{ending}")
            changed = True
    if changed:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("".join(lines))


COMPARISON_HEADING = "## Compared with video generation"
REAL_CLIP_HEADING = "## Real clip"


def record_real_clip(depth_to_metric_s, smooth_s, dof_s, layers, peak_gib,
                     path=None):
    """Write the real clip section of the node speed document.

    Rewrites the section of docs/node-speed.md (or path) that starts at the
    line "## Real clip" and runs up to the next line starting with "## " (or
    to the end of the file). If the section is missing it is inserted just
    before the "## Compared with video generation" heading, or appended if
    that is missing too. depth_to_metric_s, smooth_s and dof_s are in seconds
    (1 decimal), layers is the largest Depth of Field layer count used and
    peak_gib is the peak GPU memory in GiB (2 decimals). Other lines stay
    untouched. Only benchmark tests may call it.

    Returns None.
    """
    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "node-speed.md")
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = f.read().splitlines(keepends=True)
    section = [
        f"{REAL_CLIP_HEADING}\n",
        "\n",
        f"Measured on the saved real clip ({BENCH_FRAMES} frames at"
        f" {BENCH_WIDTH}x{BENCH_HEIGHT}).\n",
        "\n",
        "| measure | measured | standalone limit | ComfyUI target |\n",
        "| --- | --- | --- | --- |\n",
        f"| Depth to Metric (s) | {depth_to_metric_s:.1f} | 10 | |\n",
        f"| Temporal Smooth (s) | {smooth_s:.1f} | 6 | 10 |\n",
        f"| Depth of Field (s) | {dof_s:.1f} | 20 | 30 |\n",
        f"| Depth of Field layers (largest used) | {layers} | | |\n",
        f"| Peak GPU memory (GiB) | {peak_gib:.2f} | 8 | |\n",
    ]
    start = None
    for i, line in enumerate(lines):
        if line.rstrip("\r\n") == REAL_CLIP_HEADING:
            start = i
            break
    if start is not None:
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("## "):
                end = j
                break
        if end < len(lines):
            section.append("\n")
        lines[start:end] = section
    else:
        at = len(lines)
        for i, line in enumerate(lines):
            if line.rstrip("\r\n") == COMPARISON_HEADING:
                at = i
                break
        if at == len(lines):
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            if lines:
                section.insert(0, "\n")
        else:
            section.append("\n")
        lines[at:at] = section
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))


def record_comparison(dof_seconds, generation_seconds=70.7,
                      label="LTX-2 19B Q4_K_M, warm", path=None):
    """Write the Depth of Field vs video generation comparison section.

    Rewrites the section of docs/node-speed.md (or path) that starts at the
    line "## Compared with video generation" and runs to the end of the file,
    or appends it if missing. dof_seconds and generation_seconds are in
    seconds (1 decimal); the cost is 100 * dof_seconds / generation_seconds
    percent (1 decimal). Lines before the section stay untouched. Only
    benchmark tests may call it.

    Returns None.
    """
    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "node-speed.md")
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = f.read().splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.rstrip("\r\n") == COMPARISON_HEADING:
            lines = lines[:i]
            break
    else:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        if lines:
            lines.append("\n")
    percent = 100 * dof_seconds / generation_seconds
    lines.append(
        f"{COMPARISON_HEADING}\n\n"
        f"Depth of Field on {BENCH_FRAMES} frames at {BENCH_WIDTH}x{BENCH_HEIGHT}"
        f" took {dof_seconds:.1f} s; generating the same {BENCH_FRAMES}-frame"
        f" clip with {label} took {generation_seconds:.1f} s"
        f" (docs/benchmarks.md), so Depth of Field costs {percent:.1f}% of the"
        f" generation time.\n")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))
