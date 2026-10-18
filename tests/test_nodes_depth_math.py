import unittest

import torch

import open_optics_nodes
from open_optics_nodes.depth_to_metric import (
    OpenOptics_DepthToMetric, depth_percentile_range, depth_to_metric_tensor)


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


class DepthToMetricTensorTests(unittest.TestCase):
    def _check(self, out, expected):
        self.assertEqual(len(out), len(expected))
        for o, e in zip(out.tolist(), expected):
            self.assertAlmostEqual(o, e, delta=1e-5)

    def test_inverse_true_values(self):
        out = depth_to_metric_tensor(torch.tensor([0.0, 0.5, 1.0]), 1, 5, True, 0, 100)
        self._check(out, [5.0, 1.666667, 1.0])

    def test_inverse_false_values(self):
        out = depth_to_metric_tensor(torch.tensor([0.0, 0.5, 1.0]), 1, 5, False, 0, 100)
        self._check(out, [1.0, 3.0, 5.0])

    def test_constant_map(self):
        for inv in (True, False):
            out = depth_to_metric_tensor(torch.full((2, 4, 4), 0.7), 1, 5, inv, 0, 100)
            self.assertEqual(out.shape, (2, 4, 4))
            self._check(out.reshape(-1), [3.0] * 32)

    def test_clamp_outside_fitted_range(self):
        out = depth_to_metric_tensor(torch.linspace(0, 1, 101), 1, 5, True, 25, 75)
        self.assertGreaterEqual(out.min().item(), 1)
        self.assertLessEqual(out.max().item(), 5)
        self.assertAlmostEqual(out[0].item(), 5.0, delta=1e-5)
        self.assertAlmostEqual(out[100].item(), 1.0, delta=1e-5)


class DepthToMetricNodeTests(unittest.TestCase):
    def test_convert_smoke(self):
        depth = torch.tensor([[[0.0, 0.5, 1.0]]])
        z, preview = OpenOptics_DepthToMetric().convert(1.0, 5.0, True, 0.0, 100.0, depth_mask=depth)
        self.assertEqual(z.shape, (1, 1, 3))
        for o, e in zip(z.reshape(-1).tolist(), [5.0, 1.666667, 1.0]):
            self.assertAlmostEqual(o, e, delta=1e-5)
        self.assertEqual(preview.shape, (1, 1, 3, 3))
        self.assertEqual(preview.dtype, torch.float32)
        self.assertAlmostEqual(preview[0, 0, 0, 0].item(), 0.0, delta=1e-6)
        self.assertAlmostEqual(preview[0, 0, 2, 2].item(), 1.0, delta=1e-6)

    def test_registration(self):
        self.assertIs(open_optics_nodes.NODE_CLASS_MAPPINGS["OpenOptics_DepthToMetric"],
                      OpenOptics_DepthToMetric)
        self.assertEqual(open_optics_nodes.NODE_DISPLAY_NAME_MAPPINGS["OpenOptics_DepthToMetric"],
                         "Open Optics: Depth to Metric")


if __name__ == "__main__":
    unittest.main()
