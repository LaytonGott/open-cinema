import unittest

import torch

from open_optics_nodes.depth_to_metric import depth_percentile_range


class DepthPercentileRangeTests(unittest.TestCase):
    def test_linspace_2_98(self):
        lo, hi = depth_percentile_range(torch.linspace(0, 1, 101), 2, 98)
        self.assertAlmostEqual(lo, 0.02, delta=1e-6)
        self.assertAlmostEqual(hi, 0.98, delta=1e-6)

    def test_linspace_full_range(self):
        lo, hi = depth_percentile_range(torch.linspace(0, 1, 101), 0, 100)
        self.assertAlmostEqual(lo, 0.0, delta=1e-6)
        self.assertAlmostEqual(hi, 1.0, delta=1e-6)

    def test_whole_batch_pooled(self):
        depth = torch.zeros(2, 4, 4)
        depth[1] = 1.0
        lo, hi = depth_percentile_range(depth, 0, 100)
        self.assertAlmostEqual(lo, 0.0, delta=1e-6)
        self.assertAlmostEqual(hi, 1.0, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
