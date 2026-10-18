"""Seeded synthetic flicker sequences for temporal tests (standard library only)."""

import math
import random


def make_flicker_sequence(seed=0, frames=40, height=8, width=8,
                          gain=0.10, noise=0.05, dropout=0.03, spike=0.02):
    """Build a noisy depth sequence of a static two-plane scene.

    Depths are in metres: the top half of the rows is 2.0 m, the bottom half
    6.0 m. Frame t is scaled by 1 + gain*sin(2*pi*t/12), each pixel gets
    multiplicative uniform noise of +-noise, then with probability dropout it
    becomes 0.0, else with probability spike it becomes 3.0 times the true
    depth. Only random.Random(seed) is used.

    Returns (noisy, truth): two lists of frames, each frame a list of rows of
    floats in metres.
    """
    rng = random.Random(seed)
    frame_truth = [[2.0 if r < height // 2 else 6.0] * width for r in range(height)]
    truth = [[list(row) for row in frame_truth] for _ in range(frames)]
    noisy = []
    for t in range(frames):
        gain_t = 1.0 + gain * math.sin(2.0 * math.pi * t / 12.0)
        frame = []
        for r in range(height):
            row = []
            for c in range(width):
                true_d = truth[t][r][c]
                value = true_d * gain_t * (1.0 + rng.uniform(-noise, noise))
                if rng.random() < dropout:
                    value = 0.0
                elif rng.random() < spike:
                    value = 3.0 * true_d
                row.append(value)
            frame.append(row)
        noisy.append(frame)
    return noisy, truth


def count_flicker(noisy, truth):
    """Count corrupted pixels in a noisy depth sequence (depths in metres).

    Returns a dict {'dropouts': number of values equal to 0.0,
    'spikes': number of values greater than 2.5 times the true depth}.
    """
    dropouts = 0
    spikes = 0
    for nf, tf in zip(noisy, truth):
        for nrow, trow in zip(nf, tf):
            for n, t in zip(nrow, trow):
                if n == 0.0:
                    dropouts += 1
                elif n > 2.5 * t:
                    spikes += 1
    return {'dropouts': dropouts, 'spikes': spikes}
