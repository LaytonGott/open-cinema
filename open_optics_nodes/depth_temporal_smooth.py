"""Temporal depth smoothing node for Open Optics (CPU torch tensors)."""

import time

import torch

from open_optics.temporal import smooth_depth_sequence
from open_optics_nodes import common
from open_optics_nodes.device import get_device


class OpenOptics_DepthTemporalSmooth:
    """Smooth a metric depth sequence over time.

    depth is metric depth in metres, a MASK [B, H, W] where the batch is the
    frame sequence. strength runs from 0 to 1: 0 passes the depth through, 1
    is the smoothest. Missing values (nan, inf, zero, negative) and one-frame
    spikes are ignored; persistent changes are followed within a few frames.
    Returns a float32 MASK [B, H, W] of depth in metres. Tip: smooth the depth
    first, then connect the result to the Depth of Field node.
    """

    DESCRIPTION = (
        "Smooths metric depth over time. depth is in metres, with the batch "
        "as the frame sequence. strength 0 to 1: 0 passes through, 1 is "
        "smoothest. Ignores missing values (nan, inf, zero, negative) and "
        "one-frame spikes; persistent changes are followed within a few "
        "frames. Returns a MASK [B, H, W] float32 in metres. Tip: smooth the "
        "depth first, then connect the result to the Depth of Field node."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "depth": ("MASK",),
                "strength": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.01}),
                "chunk_frames": common.CHUNK_FRAMES_INPUT,
            },
        }

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("depth_m",)
    FUNCTION = "smooth"
    CATEGORY = "Open Optics"

    def smooth(self, depth, strength=0.7, chunk_frames=8):
        """Smooth a depth sequence over time.

        depth is a MASK [B, H, W] of depth in metres (one frame per batch
        entry); strength is unitless, 0 to 1. The core smooths the whole
        sequence in order; chunk_frames (a count of frames, >= 1, default 8)
        is how many result frames are moved through get_device() at a time and
        does not change the result. Returns a 1-tuple holding a float32 CPU
        MASK [B, H, W] of smoothed depth in metres. Raises ValueError if depth
        is not a 3-dimensional tensor or chunk_frames is invalid.
        """
        t0 = time.perf_counter()
        common.check_chunk_frames(chunk_frames)
        if not isinstance(depth, torch.Tensor):
            got = type(depth).__name__
        elif depth.dim() != 3:
            got = f"{depth.dim()} dimensions"
        else:
            got = None
        if got is not None:
            raise ValueError(
                f"depth must be a 3-dimensional tensor [B, H, W], got {got}"
            )
        frames = depth.detach().cpu().to(torch.float64).tolist()
        out = smooth_depth_sequence(frames, strength)
        if depth.shape[0] == 0:
            common.log_call("OpenOptics_DepthTemporalSmooth", torch.zeros(0, device=get_device()),
                            0, chunk_frames, time.perf_counter() - t0)
            return (torch.zeros(depth.shape, dtype=torch.float32),)
        device = get_device()
        chunks = []
        worked_on = None
        for start, stop in common.chunk_ranges(depth.shape[0], chunk_frames):
            chunk = torch.tensor(out[start:stop], dtype=torch.float32)
            chunk = chunk.reshape((stop - start,) + tuple(depth.shape[1:]))
            chunk = chunk.to(device)
            worked_on = chunk
            chunks.append(chunk.cpu().to(torch.float32))
        result = torch.cat(chunks)
        common.log_call("OpenOptics_DepthTemporalSmooth", worked_on, depth.shape[0], chunk_frames,
                        time.perf_counter() - t0)
        return (result,)
