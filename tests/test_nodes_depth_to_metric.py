import unittest

import torch

from open_optics.depth import depth_to_metric
from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField
from open_optics_nodes.depth_to_metric import OpenOptics_DepthToMetric, _validate_subject_params


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

    def test_error_messages_name_inputs(self):
        node = OpenOptics_DepthToMetric()
        d = torch.rand(1, 4, 4)
        img = torch.rand(1, 4, 4, 3)
        with self.assertRaisesRegex(ValueError, "near_m"):
            node.convert(near_m=0.0, far_m=5.0, depth_mask=d)
        for far in (1.0, 0.5):
            with self.assertRaisesRegex(ValueError, "far_m"):
                node.convert(near_m=1.0, far_m=far, depth_mask=d)
        for lo, hi in ((50.0, 50.0), (60.0, 40.0), (0.0, 101.0)):
            with self.assertRaisesRegex(ValueError, "percentile"):
                node.convert(low_percentile=lo, high_percentile=hi, depth_mask=d)
        with self.assertRaisesRegex(ValueError, "depth_mask"):
            node.convert()
        with self.assertRaisesRegex(ValueError, "depth_mask"):
            node.convert(depth_mask=d, depth_image=img)

    def test_mask_feeds_depth_of_field(self):
        d = torch.rand(1, 16, 16)
        z, _ = OpenOptics_DepthToMetric().convert(depth_mask=d)
        image = torch.rand(1, 16, 16, 3)
        out, mask = OpenOptics_DepthOfField().apply(image, depth_mask=z)
        self.assertEqual(tuple(out.shape), (1, 16, 16, 3))
        self.assertEqual(tuple(mask.shape), (1, 16, 16))

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

    def test_full_range_mask_values(self):
        d = torch.tensor([[[0.0, 0.5, 1.0]]])
        z, _ = _convert(d, inverse_depth=True)
        # 1/Z = 0.2 + 0.8 d, so d = 0.5 gives 1 / 0.6 by hand.
        for got, want in zip(z[0, 0].tolist(), [5.0, 1.0 / 0.6, 1.0]):
            self.assertAlmostEqual(got, want, places=5)
        z, _ = _convert(d, inverse_depth=False)
        for got, want in zip(z[0, 0].tolist(), [1.0, 3.0, 5.0]):
            self.assertAlmostEqual(got, want, places=5)

    def test_percentile_clamping(self):
        d = torch.tensor([[[i / 100.0 for i in range(101)]]])
        z, _ = _convert(d, inverse_depth=True, low_percentile=10.0, high_percentile=90.0)
        vals = z[0, 0].tolist()
        for i in range(0, 10):  # below the 10th percentile (0.10)
            self.assertAlmostEqual(vals[i], 5.0, places=5)
        for i in range(91, 101):  # above the 90th percentile (0.90)
            self.assertAlmostEqual(vals[i], 1.0, places=5)
        self.assertGreaterEqual(min(vals), 1.0 - 1e-6)
        self.assertLessEqual(max(vals), 5.0 + 1e-6)

    def test_default_percentiles_values(self):
        # 101-value ramp: 2nd and 98th percentiles are 0.02 and 0.98 by hand.
        d = torch.tensor([[[i / 100.0 for i in range(101)]]])
        z, _ = OpenOptics_DepthToMetric().convert(near_m=1.0, far_m=5.0, depth_mask=d)
        a = (1.0 / 1.0 - 1.0 / 5.0) / 0.96
        b = 1.0 / 1.0 - a * 0.98
        self.assertAlmostEqual(float(z[0, 0, 50]), 1.0 / (a * 0.5 + b), places=5)
        self.assertAlmostEqual(float(z[0, 0, 0]), 5.0, places=5)
        self.assertAlmostEqual(float(z[0, 0, 100]), 1.0, places=5)

    def test_preview_grey_near_bright(self):
        d = torch.tensor([[[0.0, 1.0]]])
        z, preview = _convert(d, inverse_depth=True)
        self.assertAlmostEqual(float(z[0, 0, 1]), 1.0, places=5)
        self.assertAlmostEqual(float(z[0, 0, 0]), 5.0, places=5)
        self.assertAlmostEqual(float(preview[0, 0, 1, 0]), 1.0, places=5)
        self.assertAlmostEqual(float(preview[0, 0, 0, 0]), 0.0, places=5)
        self.assertTrue(torch.equal(preview[..., 0], preview[..., 1]))
        self.assertTrue(torch.equal(preview[..., 1], preview[..., 2]))


class TestDepthToMetricDefaults(unittest.TestCase):
    def test_input_defaults(self):
        req = OpenOptics_DepthToMetric.INPUT_TYPES()["required"]
        self.assertEqual(req["near_m"][1]["default"], 0.5)
        self.assertEqual(req["far_m"][1]["default"], 10.0)
        self.assertEqual(req["inverse_depth"][1]["default"], True)
        self.assertEqual(req["low_percentile"][1]["default"], 2.0)
        self.assertEqual(req["high_percentile"][1]["default"], 98.0)

    def test_chunk_frames_input(self):
        req = OpenOptics_DepthToMetric.INPUT_TYPES()["required"]
        self.assertEqual(req["chunk_frames"][0], "INT")
        self.assertEqual(req["chunk_frames"][1]["default"], 8)
        self.assertEqual(req["chunk_frames"][1]["min"], 1)

    def test_chunk_frames_zero_raises(self):
        with self.assertRaisesRegex(ValueError, "chunk_frames"):
            OpenOptics_DepthToMetric().convert(depth_mask=torch.rand(1, 4, 4), chunk_frames=0)

    def test_chunk_sizes_match_full(self):
        g = torch.Generator().manual_seed(3)
        d = torch.rand(5, 6, 7, generator=g)
        before = d.clone()
        node = OpenOptics_DepthToMetric()
        z_full, p_full = node.convert(depth_mask=d, chunk_frames=5)
        for size in (1, 3):
            with self.subTest(chunk_frames=size):
                z, p = node.convert(depth_mask=d, chunk_frames=size)
                self.assertTrue(torch.allclose(z, z_full, atol=1e-5))
                self.assertTrue(torch.allclose(p, p_full, atol=1e-5))
        self.assertTrue(torch.equal(d, before))

    def test_outputs_are_cpu_float32(self):
        z, p = OpenOptics_DepthToMetric().convert(depth_mask=torch.rand(3, 4, 4), chunk_frames=2)
        for t in (z, p):
            self.assertEqual(t.device.type, "cpu")
            self.assertEqual(t.dtype, torch.float32)

    def test_default_convert_on_ramp(self):
        # 101-value ramp: d_lo = 0.02, d_hi = 0.98 by hand.
        d = torch.tensor([[[i / 100.0 for i in range(101)]]])
        z, _ = OpenOptics_DepthToMetric().convert(depth_mask=d)
        a = (1.0 / 0.5 - 1.0 / 10.0) / 0.96
        b = 2.0 - a * 0.98
        self.assertAlmostEqual(float(z[0, 0, 100]), 0.5, places=5)
        self.assertAlmostEqual(float(z[0, 0, 0]), 10.0, places=5)
        self.assertAlmostEqual(float(z[0, 0, 50]), 1.0 / (a * 0.5 + b), places=5)
        self.assertAlmostEqual(float(z[0, 0, 98]), 0.5, places=5)
        self.assertAlmostEqual(float(z[0, 0, 2]), 10.0, places=5)


class TestDepthToMetricOutputs(unittest.TestCase):
    def test_preview_monotonic(self):
        d = torch.tensor([[[i / 10.0 for i in range(11)]]])
        z, preview = _convert(d)
        zs = z[0, 0].tolist()
        ps = preview[0, 0, :, 0].tolist()
        for zi, pi in zip(zs, ps):
            if abs(zi - 1.0) < 1e-5:
                self.assertAlmostEqual(pi, 1.0, delta=1e-5)
            if abs(zi - 5.0) < 1e-5:
                self.assertAlmostEqual(pi, 0.0, delta=1e-5)
        self.assertAlmostEqual(min(zs), 1.0, delta=1e-5)
        self.assertAlmostEqual(max(zs), 5.0, delta=1e-5)
        pairs = sorted(zip(zs, ps), key=lambda t: -t[0])  # z decreasing
        for (_, p0), (_, p1) in zip(pairs, pairs[1:]):
            self.assertGreaterEqual(p1, p0 - 1e-6)

    def test_forms_agree_both_outputs(self):
        d = torch.tensor([[[i / 10.0 for i in range(11)]]])
        img = d.unsqueeze(-1).repeat(1, 1, 1, 3)
        node = OpenOptics_DepthToMetric()
        kw = dict(near_m=1.0, far_m=5.0, inverse_depth=True,
                  low_percentile=0.0, high_percentile=100.0)
        z1, p1 = node.convert(depth_mask=d, **kw)
        z2, p2 = node.convert(depth_image=img, **kw)
        self.assertTrue(torch.allclose(z1, z2, atol=1e-6))
        self.assertTrue(torch.allclose(p1, p2, atol=1e-6))

    def test_mask_output_feeds_dof_same_as_direct(self):
        g = torch.Generator().manual_seed(0)
        d = torch.rand(1, 16, 16, generator=g)
        image = torch.rand(1, 16, 16, 3, generator=g)
        z, _ = OpenOptics_DepthToMetric().convert(depth_mask=d)
        dof = OpenOptics_DepthOfField()
        out1, m1 = dof.apply(image, depth_mask=z)
        out2, m2 = dof.apply(image, depth_image=z.unsqueeze(-1).repeat(1, 1, 1, 3))
        self.assertTrue(torch.allclose(out1, out2, atol=1e-5))
        self.assertTrue(torch.allclose(m1, m2, atol=1e-5))


class TestDepthToMetricRobustness(unittest.TestCase):
    def test_nan_input_finite_in_range(self):
        d = torch.linspace(0.0, 1.0, 16).reshape(1, 4, 4).clone()
        d[0, 1, 1] = float("nan")
        d[0, 2, 2] = float("inf")
        for inv in (True, False):
            z, preview = _convert(d, inverse_depth=inv)
            self.assertTrue(torch.isfinite(z).all())
            self.assertGreaterEqual(float(z.min()), 1.0 - 1e-5)
            self.assertLessEqual(float(z.max()), 5.0 + 1e-5)
            self.assertTrue(torch.isfinite(preview).all())
            self.assertGreaterEqual(float(preview.min()), 0.0)
            self.assertLessEqual(float(preview.max()), 1.0)

    def test_each_bad_param_raises(self):
        d = torch.rand(1, 4, 4)
        cases = [
            (dict(near_m=0.0, far_m=5.0), "near_m"),
            (dict(near_m=1.0, far_m=1.0), "far_m"),
            (dict(near_m=1.0, far_m=0.5), "far_m"),
            (dict(low_percentile=60.0, high_percentile=40.0), "percentile"),
            (dict(low_percentile=50.0, high_percentile=50.0), "percentile"),
            (dict(low_percentile=0.0, high_percentile=101.0), "percentile"),
        ]
        for kw, name in cases:
            with self.subTest(kw=kw):
                with self.assertRaisesRegex(ValueError, name):
                    OpenOptics_DepthToMetric().convert(depth_mask=d, **kw)


class TestDepthToMetricBatchFit(unittest.TestCase):
    def test_batch_equals_concatenated_fit(self):
        f0 = torch.linspace(0.0, 1.0, 12).reshape(3, 4)
        f1 = torch.linspace(0.0, 0.4, 12).reshape(3, 4)
        d = torch.stack([f0, f1])  # [2, 3, 4]
        one = d.reshape(1, 6, 4)
        node = OpenOptics_DepthToMetric()
        for inv in (True, False):
            with self.subTest(inverse_depth=inv):
                z, _ = node.convert(near_m=1.0, far_m=5.0, inverse_depth=inv, depth_mask=d)
                z1, _ = node.convert(near_m=1.0, far_m=5.0, inverse_depth=inv, depth_mask=one)
                self.assertTrue(torch.allclose(z.reshape(1, 6, 4), z1, atol=1e-5))

    def test_same_value_same_metres_across_frames(self):
        f0 = torch.linspace(0.0, 1.0, 12).reshape(3, 4)
        f1 = torch.linspace(0.0, 0.4, 12).reshape(3, 4)
        d = torch.stack([f0, f1])
        d[0, 1, 1] = 0.3
        d[1, 2, 3] = 0.3
        for inv in (True, False):
            with self.subTest(inverse_depth=inv):
                z, _ = OpenOptics_DepthToMetric().convert(
                    near_m=1.0, far_m=5.0, inverse_depth=inv, depth_mask=d)
                self.assertAlmostEqual(float(z[0, 1, 1]), float(z[1, 2, 3]), delta=1e-5)

    def test_constant_map_midpoint(self):
        d = torch.full((2, 4, 4), 0.7)
        img = d.unsqueeze(-1).repeat(1, 1, 1, 3)
        node = OpenOptics_DepthToMetric()
        for inv in (True, False):
            for kw in (dict(depth_mask=d), dict(depth_image=img)):
                with self.subTest(inverse_depth=inv, form=next(iter(kw))):
                    z, _ = node.convert(near_m=1.0, far_m=5.0, inverse_depth=inv, **kw)
                    for v in z.flatten().tolist():
                        self.assertAlmostEqual(v, 3.0, delta=1e-5)


class TestDepthToMetricSubjectInputs(unittest.TestCase):
    def _required(self):
        return OpenOptics_DepthToMetric.INPUT_TYPES()["required"]

    def test_mode_choices_and_default(self):
        spec = self._required()["mode"]
        self.assertEqual(list(spec[0]), ["near_far", "subject"])
        self.assertEqual(spec[1]["default"], "near_far")

    def test_subject_defaults(self):
        req = self._required()
        self.assertAlmostEqual(req["subject_m"][1]["default"], 3.0, places=6)
        self.assertAlmostEqual(req["subject_x"][1]["default"], 0.5, places=6)
        self.assertAlmostEqual(req["subject_y"][1]["default"], 0.5, places=6)
        self.assertEqual(req["subject_radius_px"][1]["default"], 4)

    def test_near_far_default_mode_values(self):
        d = torch.tensor([[[0.0, 0.5, 1.0]]])
        z, _ = _convert(d)
        for got, want in zip(z[0, 0].tolist(), [5.0, 1.666667, 1.0]):
            self.assertAlmostEqual(got, want, places=5)


class TestDepthToMetricSubjectValidation(unittest.TestCase):
    D = torch.tensor([[[0.0, 0.5, 1.0]]])

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            _convert(self.D, mode="bogus")

    def test_subject_m_zero(self):
        with self.assertRaises(ValueError):
            _convert(self.D, mode="subject", subject_m=0.0)

    def test_subject_m_below_near(self):
        with self.assertRaises(ValueError):
            _convert(self.D, mode="subject", subject_m=0.5)

    def test_subject_m_above_far(self):
        with self.assertRaises(ValueError):
            _convert(self.D, mode="subject", subject_m=6.0)

    def test_subject_x_out_of_range(self):
        with self.assertRaises(ValueError):
            _convert(self.D, mode="subject", subject_x=1.5)

    def test_subject_y_out_of_range(self):
        with self.assertRaises(ValueError):
            _convert(self.D, mode="subject", subject_y=-0.1)

    def test_subject_radius_negative(self):
        with self.assertRaises(ValueError):
            _convert(self.D, mode="subject", subject_radius_px=-1)

    def test_valid_values_do_not_raise(self):
        _validate_subject_params("subject", 3.0, 1.0, 5.0, 0.5, 0.5, 4)


if __name__ == "__main__":
    unittest.main()
