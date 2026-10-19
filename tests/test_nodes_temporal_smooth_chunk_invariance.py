import itertools
import os
import unittest
from unittest import mock

import torch

from open_optics_nodes.depth_temporal_smooth import OpenOptics_DepthTemporalSmooth
from tests.test_nodes_depth_temporal_smooth_reference import make_depth

TOLERANCE = 1e-4


class TestTemporalSmoothChunkInvariance(unittest.TestCase):
    def check(self, device):
        depth = make_depth()
        node = OpenOptics_DepthTemporalSmooth()
        outputs = {}
        try:
            with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": device}):
                for c in (1, 3, depth.shape[0]):
                    (out,) = node.smooth(depth, strength=0.7, chunk_frames=c)
                    self.assertEqual(out.dtype, torch.float32)
                    self.assertEqual(out.device.type, "cpu")
                    self.assertEqual(tuple(out.shape), tuple(depth.shape))
                    outputs[c] = out
            for a, b in itertools.combinations(outputs, 2):
                with self.subTest(device=device, chunks=(a, b)):
                    oa, ob = outputs[a], outputs[b]
                    nan_a = torch.isnan(oa)
                    self.assertTrue(torch.equal(nan_a, torch.isnan(ob)))
                    diff = (oa - ob)[~nan_a].abs()
                    if diff.numel():
                        self.assertLess(diff.max().item(), TOLERANCE)
        finally:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def test_chunk_invariance_cpu(self):
        self.check("cpu")

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is not available")
    def test_chunk_invariance_cuda(self):
        self.check("cuda")


if __name__ == "__main__":
    unittest.main()
