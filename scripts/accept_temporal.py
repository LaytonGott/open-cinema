"""Goal check: temporal depth stability. Run with: node scripts/run-py.js scripts/accept_temporal.py

Builds synthetic flickering depth sequences (nested lists, metres) with a fixed seed and checks that
open_optics.temporal.smooth_depth_sequence(frames) removes the flicker, keeps the scene's depth, follows a real depth
change within a few frames, copes with invalid values, and does not modify its input.
Prints one line per problem and exits 1 if there is any.
"""
import copy
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

problems = []


def check(ok, message):
    if not ok:
        problems.append(message)


try:
    from open_optics.temporal import smooth_depth_sequence
except Exception as exc:
    print(f"cannot import open_optics.temporal.smooth_depth_sequence: {exc}")
    sys.exit(1)

H, W, N = 8, 8, 30


def truth(row, col):
    return 2.0 if col < W // 2 else 6.0


def flicker_sequence(seed):
    rng = random.Random(seed)
    frames = []
    for t in range(N):
        gain = 1.0 + 0.10 * math.sin(2.1 * t)  # a global shimmer of +-10 %
        frame = []
        for r in range(H):
            row = []
            for c in range(W):
                value = truth(r, c) * gain * (1.0 + rng.uniform(-0.05, 0.05))  # +-5 % per-pixel noise
                roll = rng.random()
                if roll < 0.03:
                    value = 0.0  # dropout
                elif roll < 0.05:
                    value *= 3.0  # spike
                row.append(value)
            frame.append(row)
        frames.append(frame)
    return frames


def mean_abs_change(frames, start):
    total, count = 0.0, 0
    for t in range(start + 1, len(frames)):
        for r in range(H):
            for c in range(W):
                total += abs(frames[t][r][c] - frames[t - 1][r][c])
                count += 1
    return total / count


def mean_rel_error(frames, start):
    total, count = 0.0, 0
    for t in range(start, len(frames)):
        for r in range(H):
            for c in range(W):
                total += abs(frames[t][r][c] - truth(r, c)) / truth(r, c)
                count += 1
    return total / count


def well_formed(frames, n):
    return (isinstance(frames, list) and len(frames) == n and all(isinstance(f, list) and len(f) == H for f in frames)
            and all(isinstance(row, list) and len(row) == W for f in frames for row in f)
            and all(isinstance(v, float) and math.isfinite(v) and v > 0 for f in frames for row in f for v in row))


for seed in (1, 2, 3):
    source = flicker_sequence(seed)
    kept = copy.deepcopy(source)
    out = smooth_depth_sequence(source)
    check(source == kept, f"seed {seed}: the input sequence was modified")
    if not well_formed(out, N):
        problems.append(f"seed {seed}: the output must be a list of {N} frames of {H}x{W} nested lists of positive finite floats")
        continue
    before, after = mean_abs_change(source, 5), mean_abs_change(out, 5)
    check(after <= 0.4 * before, f"seed {seed}: frame-to-frame change only fell from {before:.3f} to {after:.3f} (need at most 40 %)")
    err = mean_rel_error(out, 5)
    check(err <= 0.06, f"seed {seed}: the smoothed depth is off the true depth by {err:.1%} on average (need at most 6 %)")

# A real depth change must be followed, not smoothed away.
step = [[[2.0] * W for _ in range(H)] for _ in range(10)] + [[[4.0] * W for _ in range(H)] for _ in range(10)]
out = smooth_depth_sequence(step)
if well_formed(out, 20):
    check(abs(out[9][0][0] - 2.0) / 2.0 <= 0.02, f"before the change the depth should stay at 2 m; got {out[9][0][0]:.3f}")
    check(abs(out[14][0][0] - 4.0) / 4.0 <= 0.15, f"five frames after a step from 2 m to 4 m the depth should be within 15 % of 4 m; got {out[14][0][0]:.3f}")
else:
    problems.append("the step sequence did not give a well-formed output")

# Invalid values (nan, inf, zero, negative) are treated as missing.
bad = [[[3.0] * W for _ in range(H)] for _ in range(12)]
bad[5][2][3] = float("nan")
bad[6][4][4] = float("inf")
bad[7][0][0] = 0.0
bad[8][1][1] = -2.0
out = smooth_depth_sequence(bad)
if well_formed(out, 12):
    check(all(abs(out[t][r][c] - 3.0) < 0.5 for t in range(12) for r in range(H) for c in range(W)), "invalid values (nan, inf, 0, negative) leaked into the output")
else:
    problems.append("a sequence with invalid values gave a malformed output (NaN, inf or non-positive values must not appear)")

# Edge cases: no frames, one frame.
check(smooth_depth_sequence([]) == [], "an empty sequence must give an empty list")
one = [[[2.5] * W for _ in range(H)]]
check(smooth_depth_sequence(one) == one, "a single frame must come back unchanged")

for p in problems:
    print(p)
print("temporal smoothing: OK" if not problems else f"temporal smoothing: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
