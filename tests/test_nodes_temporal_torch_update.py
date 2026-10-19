import unittest

import torch

from open_optics.temporal import smooth_depth_sequence
from open_optics_nodes.temporal_torch import _update_frame

NAN = float("nan")


def _frames():
    base = [[1.0 + 0.5 * (3 * r + c) for c in range(3)] for r in range(3)]

    def scaled(k):
        return [[x * k for x in row] for row in base]

    def blank(val):
        return [[val] * 3 for _ in range(3)]

    spike = scaled(1.0)
    spike[1][1] = base[1][1] * 10  # one-frame spike
    spike[0][0] = base[0][0] * 0.1
    mixed = scaled(1.0)
    mixed[2][2] = NAN
    mixed[0][1] = 0.0
    return [
        scaled(1.0),
        spike,
        scaled(1.02),
        scaled(3.0),  # persistent step, frame 1 of 2
        scaled(3.0),  # frame 2 of 2: accepted
        blank(NAN),
        blank(0.0),
        mixed,
    ]


class UpdateFrameTest(unittest.TestCase):
    def test_matches_reference(self):
        frames = _frames()
        strength = 0.7
        ref = smooth_depth_sequence(frames, strength)
        gain = 1 - 0.9 * strength
        shape = (3, 3)
        est = torch.full(shape, NAN, dtype=torch.float64)
        pending = torch.full(shape, NAN, dtype=torch.float64)
        first_val = torch.full(shape, NAN, dtype=torch.float64)
        first_t = torch.full(shape, -1, dtype=torch.int64)
        for t, frame in enumerate(frames):
            v = torch.tensor(frame, dtype=torch.float64)
            out = _update_frame(est, pending, first_val, first_t, v, t, gain)
            self.assertEqual(out.dtype, torch.float64)
            for r in range(3):
                for c in range(3):
                    exp = ref[t][r][c]
                    got = out[r, c].tolist()
                    if exp != exp:
                        self.assertTrue(got != got, (t, r, c))
                    else:
                        self.assertAlmostEqual(got, exp, delta=1e-6)
        self.assertTrue(bool((first_t == 0).all()))
        self.assertAlmostEqual(first_val[1, 1].tolist(), 1.0 + 0.5 * 4, delta=1e-9)


if __name__ == "__main__":
    unittest.main()
