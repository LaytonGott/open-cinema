"""Seeded synthetic frames and depth maps for benchmark tests (CPU torch)."""

import math

import torch

SUBJECT_DEPTH_M = 3.0
FOREGROUND_DEPTH_M = 1.2


def make_frames(frames, height, width, seed=0):
    """Build a smooth sinusoidal colour sequence with small gaussian noise.

    The pattern phase shifts with the frame index and the channel; noise has
    a standard deviation of 0.02 and comes from torch.Generator seeded with
    seed. Sizes are in frames and pixels; values are unitless, 0 to 1.

    Returns a float32 CPU tensor [frames, height, width, 3] clamped to 0..1.
    """
    gen = torch.Generator(device="cpu")
    gen.manual_seed(seed)
    ys = torch.arange(height, dtype=torch.float32).view(1, height, 1, 1)
    xs = torch.arange(width, dtype=torch.float32).view(1, 1, width, 1)
    ts = torch.arange(frames, dtype=torch.float32).view(frames, 1, 1, 1)
    cs = torch.arange(3, dtype=torch.float32).view(1, 1, 1, 3)
    phase = 0.3 * ts + 2.0 * math.pi / 3.0 * cs
    wave = torch.sin(2.0 * math.pi * (xs / 16.0 + ys / 24.0) + phase)
    base = 0.5 + 0.4 * wave
    noise = 0.02 * torch.randn((frames, height, width, 3), generator=gen)
    return (base + noise).clamp(0.0, 1.0).to(torch.float32)


def subject_box(height, width):
    """Return the subject rectangle (r0, r1, c0, c1) in pixels.

    Rows are 35% to 75% of height, columns 40% to 60% of width; r1 and c1
    are exclusive. All four values are ints.
    """
    return (int(0.35 * height), int(0.75 * height),
            int(0.40 * width), int(0.60 * width))


def foreground_box(height, width):
    """Return the foreground rectangle (r0, r1, c0, c1) in pixels.

    Rows are 55% to 95% of height, columns 5% to 25% of width; r1 and c1
    are exclusive. All four values are ints.
    """
    return (int(0.55 * height), int(0.95 * height),
            int(0.05 * width), int(0.25 * width))


def make_depth(frames, height, width):
    """Build a static depth sequence in metres.

    The ground plane goes linearly from 1.0 m at row 0 to 10.0 m at the last
    row; the subject box is exactly SUBJECT_DEPTH_M (3.0 m) and the
    foreground box exactly FOREGROUND_DEPTH_M (1.2 m), foreground on top.

    Returns a float32 CPU tensor [frames, height, width] in metres.
    """
    steps = max(height - 1, 1)
    rows = torch.arange(height, dtype=torch.float32) / steps
    depth = (1.0 + 9.0 * rows).view(height, 1).repeat(1, width)
    r0, r1, c0, c1 = subject_box(height, width)
    depth[r0:r1, c0:c1] = SUBJECT_DEPTH_M
    r0, r1, c0, c1 = foreground_box(height, width)
    depth[r0:r1, c0:c1] = FOREGROUND_DEPTH_M
    return depth.unsqueeze(0).repeat(frames, 1, 1).contiguous()
