import unittest

import torch

from open_optics.depth import depth_to_metric
from open_optics_nodes.depth_to_metric import OpenOptics_DepthToMetric


def _convert(depth, **kw):
    args = dict(near_m=1.0, far_m=5.0, inverse_depth=True,
                low_percentile=0.0, high_percentile=100.0)
    args.update(kw)
    return OpenOptics_DepthToMetric().convert(depth_mask=depth, **args)


class TestDepthToMetricNode(unittest.TestCase):
    def test_inverse_values(self):
        d = torch.tensor([[[1.0, 0.0, 0.5]]])
        z, _ = _convert(d, inverse_depth=True)
        for got, want in zip(z[0, 0].tolist(), [1.0, 5.0, 1.6666667]):
            self.assertAlmostEqual(got, want, delta=1e-5)

    def test_linear_values(self):
        d = torch.tensor([[[0.0, 1.0, 0.5]]])
        z, _ = _convert(d, inverse_depth=False)
        for got, want in zip(z[0, 0].tolist(), [1.0, 5.0, 3.0]):
            self.assertAlmostEqual(got, want, delta=1e-5)

    def test_constant_map(self):
        d = torch.full((1, 4, 4), 0.7)
        for inv in (True, False):
            z, _ = _convert(d, inverse_depth=inv)
            for v in z.flatten().tolist():
                self.assertAlmostEqual(v, 3.0, delta=1e-5)

    def test_batch_fitted_together(self):
        f1 = torch.tensor([[0.0, 0.5, 1.0]])
        f2 = torch.tensor([[0.0, 0.25, 0.5]])
        d = torch.stack([f1, f2])  # [2, 1, 3]
        z, _ = _convert(d, inverse_depth=False)
        # Range is 0..1 over the whole batch, so frame 2 maps only 1..3.
        for got, want in zip(z[0, 0].tolist(), [1.0, 3.0, 5.0]):
            self.assertAlmostEqual(got, want, delta=1e-5)
        for got, want in zip(z[1, 0].tolist(), [1.0, 2.0, 3.0]):
            self.assertAlmostEqual(got, want, delta=1e-5)
        zi, _ = _convert(d, inverse_depth=True)
        self.assertAlmostEqual(float(zi[1, 0, 2]), 1.6666667, delta=1e-5)
        self.assertAlmostEqual(float(zi[1, 0, 0]), 5.0, delta=1e-5)

    def test_mask_and_image_equal(self):
        d = torch.rand(2, 5, 6)
        img = d.unsqueeze(-1).repeat(1, 1, 1, 3)
        node = OpenOptics_DepthToMetric()
        z1, p1 = node.convert(near_m=1.0, far_m=5.0, depth_mask=d)
        z2, p2 = node.convert(near_m=1.0, far_m=5.0, depth_image=img)
        self.assertTrue(torch.allclose(z1, z2, atol=1e-6))
        self.assertTrue(torch.allclose(p1, p2, atol=1e-6))

    def test_errors(self):
        node = OpenOptics_DepthToMetric()
        d = torch.rand(1, 4, 4)
        img = torch.rand(1, 4, 4, 3)
        with self.assertRaises(ValueError):
            node.convert()
        with self.assertRaises(ValueError):
            node.convert(depth_mask=d, depth_image=img)
        with self.assertRaises(ValueError):
            node.convert(near_m=0.0, far_m=5.0, depth_mask=d)
        with self.assertRaises(ValueError):
            node.convert(near_m=-1.0, far_m=5.0, depth_mask=d)
        with self.assertRaises(ValueError):
            node.convert(near_m=2.0, far_m=2.0, depth_mask=d)
        with self.assertRaises(ValueError):
            node.convert(near_m=2.0, far_m=1.0, depth_mask=d)
        with self.assertRaises(ValueError):
            node.convert(low_percentile=50.0, high_percentile=50.0, depth_mask=d)
        with self.assertRaises(ValueError):
            node.convert(low_percentile=60.0, high_percentile=40.0, depth_mask=d)
        with self.assertRaises(ValueError):
            node.convert(low_percentile=0.0, high_percentile=101.0, depth_mask=d)

    def test_dtype_shape_range(self):
        d = torch.rand(2, 8, 9)
        z, preview = OpenOptics_DepthToMetric().convert(depth_mask=d)
        self.assertEqual(z.dtype, torch.float32)
        self.assertEqual(preview.dtype, torch.float32)
        self.assertEqual(tuple(z.shape), (2, 8, 9))
        self.assertEqual(tuple(preview.shape), (2, 8, 9, 3))
        self.assertGreaterEqual(float(preview.min()), 0.0)
        self.assertLessEqual(float(preview.max()), 1.0)

    def test_defaults_match_core(self):
        # 11-value ramp 0, 0.1, ..., 1: percentile position q/100*10 gives
        # d_lo = 0.2 * 0.1 = 0.02 and d_hi = 9.8 * 0.1 = 0.98 by hand.
        d = torch.tensor([[[i / 10.0 for i in range(11)]]])
        for inv in (True, False):
            z, _ = OpenOptics_DepthToMetric().convert(inverse_depth=inv, depth_mask=d)
            for i in range(11):
                want = depth_to_metric(i / 10.0, 0.02, 0.98, 0.5, 10.0, inv)
                self.assertAlmostEqual(float(z[0, 0, i]), want, delta=1e-4)


if __name__ == "__main__":
    unittest.main()
