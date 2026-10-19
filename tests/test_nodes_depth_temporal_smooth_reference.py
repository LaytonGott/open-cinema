import math
import os
import unittest
from unittest import mock

import torch

from open_optics.temporal import smooth_depth_sequence
from open_optics_nodes.depth_temporal_smooth import OpenOptics_DepthTemporalSmooth

FRAMES = 7
SIZE = 8
TOLERANCE = 1e-4


def make_depth():
    """Seeded 7 x 8 x 8 depth sequence in metres with the awkward cases."""
    gen = torch.Generator().manual_seed(1234)
    depth = 2.0 + 0.05 * torch.rand(FRAMES, SIZE, SIZE, generator=gen)
    depth[:, :, 4:] += 3.0  # persistent step edge between columns 3 and 4
    depth[3, 1, 1] = 40.0  # one-frame outlier spike
    depth[2, 2, 2] = float("nan")
    depth[0, 3, 3] = float("nan")
    depth[4, 5, 5] = 0.0
    depth[:, 6, 0] = 0.0  # never valid
    depth[5:, 7, 7] = 9.0  # persistent change
    return depth


class TestDepthTemporalSmoothReference(unittest.TestCase):
    def check(self, device):
        depth = make_depth()
        expected = smooth_depth_sequence(depth.to(torch.float64).tolist(), 0.7)
        expected = torch.tensor(expected, dtype=torch.float64)
        node = OpenOptics_DepthTemporalSmooth()
        try:
            with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": device}):
                for c in (1, 3, FRAMES):
                    with self.subTest(device=device, chunk_frames=c):
                        (out,) = node.smooth(depth, strength=0.7, chunk_frames=c)
                        self.assertEqual(out.dtype, torch.float32)
                        self.assertEqual(out.device.type, "cpu")
                        self.assertEqual(tuple(out.shape), tuple(depth.shape))
                        got = out.to(torch.float64)
                        nan_ref = torch.isnan(expected)
                        self.assertTrue(torch.equal(torch.isnan(got), nan_ref))
                        diff = (got - expected)[~nan_ref].abs()
                        if diff.numel():
                            self.assertLess(diff.max().item(), TOLERANCE)
        finally:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def test_reference_cpu(self):
        self.check("cpu")

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is not available")
    def test_reference_cuda(self):
        self.check("cuda")


if __name__ == "__main__":
    unittest.main()
