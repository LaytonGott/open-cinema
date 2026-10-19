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
