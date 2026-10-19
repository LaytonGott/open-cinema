import unittest

import torch

from tests.synth_frames import (FOREGROUND_DEPTH_M, SUBJECT_DEPTH_M,
                                foreground_box, make_depth, make_frames,
                                subject_box)

H = W = 64
N = 3


class SynthFramesTests(unittest.TestCase):
    def test_same_seed_identical(self):
        a = make_frames(N, H, W, seed=5)
        b = make_frames(N, H, W, seed=5)
        self.assertTrue(torch.equal(a, b))

    def test_different_seed_differs(self):
        a = make_frames(N, H, W, seed=5)
        b = make_frames(N, H, W, seed=6)
        self.assertFalse(torch.equal(a, b))

    def test_frames_dtype_shape_range(self):
        f = make_frames(N, H, W)
        self.assertEqual(f.dtype, torch.float32)
        self.assertEqual(tuple(f.shape), (3, 64, 64, 3))
        self.assertGreaterEqual(f.min().item(), 0.0)
        self.assertLessEqual(f.max().item(), 1.0)

    def test_depth_dtype_shape(self):
        d = make_depth(N, H, W)
        self.assertEqual(d.dtype, torch.float32)
        self.assertEqual(tuple(d.shape), (3, 64, 64))

    def test_depth_ground_ends(self):
        d = make_depth(N, H, W)
        for t in range(N):
            self.assertAlmostEqual(d[t, 0, 0].item(), 1.0, delta=0.2)
            self.assertAlmostEqual(d[t, -1, 0].item(), 10.0, delta=0.2)

    def test_depth_boxes(self):
        d = make_depth(N, H, W)
        r0, r1, c0, c1 = subject_box(H, W)
        sub = d[:, r0:r1, c0:c1]
        self.assertTrue(sub.numel() > 0)
        for v in sub.flatten().tolist():
            self.assertAlmostEqual(v, SUBJECT_DEPTH_M, delta=1e-6)
        r0, r1, c0, c1 = foreground_box(H, W)
        fg = d[:, r0:r1, c0:c1]
        self.assertTrue(fg.numel() > 0)
        for v in fg.flatten().tolist():
            self.assertAlmostEqual(v, FOREGROUND_DEPTH_M, delta=1e-6)

    def test_ground_pixel_differs_from_boxes(self):
        d = make_depth(N, H, W)
        v = d[0, H // 2, W - 1].item()
        self.assertGreater(abs(v - SUBJECT_DEPTH_M), 0.1)
        self.assertGreater(abs(v - FOREGROUND_DEPTH_M), 0.1)


if __name__ == "__main__":
    unittest.main()
