import os
import unittest

import torch

from open_optics_nodes.depth_to_metric import (
    OpenOptics_DepthToMetric,
    _map_to_metric,
    depth_percentile_range,
    depth_to_metric_tensor,
)

PARAMS = dict(near_m=0.5, far_m=10.0, inverse_depth=True, low_percentile=2.0, high_percentile=98.0)


class TestDepthToMetricChunks(unittest.TestCase):
    def setUp(self):
        self._old_device = os.environ.get("OPEN_OPTICS_DEVICE")
        os.environ["OPEN_OPTICS_DEVICE"] = "cpu"
        torch.manual_seed(5)
        depth = torch.rand(7, 16, 16) * 0.6 + 0.2
        lo, hi = depth[4].min(), depth[4].max()
        depth[4] = (depth[4] - lo) / (hi - lo) * 45.0 + 5.0
        self.depth = depth

    def tearDown(self):
        if self._old_device is None:
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
        else:
            os.environ["OPEN_OPTICS_DEVICE"] = self._old_device

    def test_chunk_independent_with_odd_frame(self):
        node = OpenOptics_DepthToMetric()
        ref = node.convert(depth_mask=self.depth, chunk_frames=7, **PARAMS)
        for chunk in (1, 3, 7):
            out = node.convert(depth_mask=self.depth, chunk_frames=chunk, **PARAMS)
            for a, b in zip(out, ref):
                self.assertEqual(a.shape, b.shape)
                self.assertLess((a - b).abs().max().item(), 1e-5)
        single = depth_to_metric_tensor(self.depth, **PARAMS)
        self.assertLess((ref[0] - single).abs().max().item(), 1e-5)

        d_lo, d_hi = depth_percentile_range(self.depth, 2.0, 98.0)
        out1 = node.convert(depth_mask=self.depth, chunk_frames=1, **PARAMS)[0]
        shared = _map_to_metric(self.depth[0:1], d_lo, d_hi, 0.5, 10.0, True)
        self.assertLess((out1[0:1] - shared).abs().max().item(), 1e-5)
        alone = depth_to_metric_tensor(self.depth[0:1], **PARAMS)
        self.assertGreater((alone - shared).abs().max().item(), 1e-3)


if __name__ == "__main__":
    unittest.main()
