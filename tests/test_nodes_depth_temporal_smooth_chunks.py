import os
import unittest

import torch

from open_optics.temporal import smooth_depth_sequence
from open_optics_nodes.depth_temporal_smooth import OpenOptics_DepthTemporalSmooth


class TestDepthTemporalSmoothChunks(unittest.TestCase):
    def setUp(self):
        self._old_device = os.environ.get("OPEN_OPTICS_DEVICE")
        os.environ["OPEN_OPTICS_DEVICE"] = "cpu"
        torch.manual_seed(11)
        base = torch.rand(16, 16) * 4.0 + 2.0
        depth = base.unsqueeze(0).repeat(9, 1, 1)
        depth += (torch.rand(9, 16, 16) - 0.5) * 0.1
        depth[5:] *= 1.8  # persistent step change from frame 5 on
        depth[3] *= 4.0  # one-frame spike
        depth[1, 2, 3] = float("nan")
        depth[4, 7, 7] = float("nan")
        depth[6, 10, 1] = float("nan")
        depth[0, 5, 5] = float("nan")
        self.depth = depth

    def tearDown(self):
        if self._old_device is None:
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
        else:
            os.environ["OPEN_OPTICS_DEVICE"] = self._old_device

    def test_chunk_boundaries_have_no_seam(self):
        node = OpenOptics_DepthTemporalSmooth()
        ref = node.smooth(depth=self.depth, strength=0.7, chunk_frames=9)[0]
        self.assertEqual(tuple(ref.shape), (9, 16, 16))
        self.assertTrue(torch.isfinite(ref).all().item())
        for chunk in (1, 3):
            out = node.smooth(depth=self.depth, strength=0.7, chunk_frames=chunk)[0]
            self.assertTrue(torch.isfinite(out).all().item())
            self.assertLess((out - ref).abs().max().item(), 1e-5)
            for f in (2, 3, 5, 6):
                self.assertLess((out[f] - ref[f]).abs().max().item(), 1e-5)
        whole = torch.tensor(
            smooth_depth_sequence(self.depth.to(torch.float64).tolist(), 0.7),
            dtype=torch.float32,
        )
        self.assertLess((ref - whole).abs().max().item(), 1e-5)


if __name__ == "__main__":
    unittest.main()
