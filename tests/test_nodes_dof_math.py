import unittest
from unittest import mock

import torch

from open_optics_nodes import dof_math
from open_optics_nodes.dof_math import coc_radius_map, composite_layers, sanitize_depth


BAD_DEPTH = [float("nan"), float("inf"), float("-inf"), 0.0, -1.0, 2.5]


class SanitizeDepthTest(unittest.TestCase):
    def test_bad_values_become_far(self):
        out = sanitize_depth(torch.tensor(BAD_DEPTH))
        self.assertEqual(out.dtype, torch.float32)
        for i in range(5):
            self.assertEqual(out[i].item(), 1000.0)
        self.assertEqual(out[5].item(), 2.5)

    def test_outputs_finite(self):
        depth = torch.tensor(BAD_DEPTH).reshape(1, 2, 3)
        radius = coc_radius_map(depth, 50, 2.8, 3.0, 36, 20)
        self.assertTrue(torch.isfinite(radius).all().item())
        img = torch.rand(1, 2, 3, 3, generator=torch.Generator().manual_seed(2))
        out = composite_layers(img, depth, radius, 4, 3.0)
        self.assertTrue(torch.isfinite(out).all().item())
        self.assertGreaterEqual(out.min().item(), 0.0)
        self.assertLessEqual(out.max().item(), 1.0)


class CocRadiusMapTest(unittest.TestCase):
    def test_in_focus_is_zero(self):
        depth = torch.full((1, 4, 64), 3.0)
        out = coc_radius_map(depth, 50, 2.8, 3.0, 36, 100)
        self.assertEqual(out.abs().max().item(), 0.0)

    def test_known_value(self):
        # 2500 / (2.8 * 2950) * 0.5 mm = 0.151332 mm; * 64 / 36 / 2
        depth = torch.full((1, 2, 64), 3.0)
        depth[0, 0, 0] = 6.0
        out = coc_radius_map(depth, 50, 2.8, 3.0, 36, 100)
        self.assertAlmostEqual(out[0, 0, 0].item(), 0.134517, delta=1e-5)

    def test_cap(self):
        depth = torch.full((1, 2, 64), 6.0)
        out = coc_radius_map(depth, 50, 2.8, 3.0, 36, 0.1)
        self.assertAlmostEqual(out[0, 0, 0].item(), 0.1, delta=1e-6)

    def test_focus_zero_and_far_side_monotonic(self):
        depth = torch.full((2, 16, 16), 3.0, dtype=torch.float32)
        depth[:, :, :5] = 1.0
        depth[:, :, 11:] = 10.0
        out = coc_radius_map(depth, 50, 2.0, 3.0, 36, 32)
        self.assertAlmostEqual(out[0, 0, 8].item(), 0.0, delta=1e-6)
        mid = coc_radius_map(torch.full((2, 16, 16), 5.0), 50, 2.0, 3.0, 36, 32)
        self.assertGreater(out[1, 3, 13].item(), mid[0, 0, 0].item())

    def test_dtype(self):
        out = coc_radius_map(torch.full((1, 2, 8), 2.0, dtype=torch.float64), 50, 2.8, 3.0, 36, 10)
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(out.shape, (1, 2, 8))


class CompositeLayersTest(unittest.TestCase):
    def test_zero_radius_identity(self):
        g = torch.Generator().manual_seed(0)
        img = torch.rand(1, 8, 8, 3, generator=g)
        depth = torch.rand(1, 8, 8, generator=g) * 10 + 1
        out = composite_layers(img, depth, torch.zeros(1, 8, 8), 4, 3.0)
        self.assertTrue(torch.allclose(out, img, atol=1e-5))

    def test_no_halo_on_sharp_foreground(self):
        img = torch.zeros(1, 8, 16, 3)
        img[:, :, :8] = 1.0
        depth = torch.full((1, 8, 16), 10.0)
        depth[:, :, :8] = 2.0
        radius = torch.zeros(1, 8, 16)
        radius[:, :, 8:] = 3.0
        out = composite_layers(img, depth, radius, 4, 3.0)
        self.assertTrue(torch.allclose(out[:, :, :8], torch.ones(1, 8, 8, 3), atol=1e-5))

    def test_one_blur_call_per_layer(self):
        img = torch.zeros(1, 8, 16, 3)
        img[:, :, :8] = 1.0
        depth = torch.full((1, 8, 16), 10.0)
        depth[:, :, :8] = 2.0
        radius = torch.zeros(1, 8, 16)
        radius[:, :, 8:] = 3.0
        channels = []
        original = dof_math.blur_layer

        def recording(x, *args, **kwargs):
            channels.append(x.shape[1])
            return original(x, *args, **kwargs)

        with mock.patch("open_optics_nodes.dof_math.blur_layer", recording):
            composite_layers(img, depth, radius, 4, 3.0)
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels, [4, 4])

    def test_constant_colour_preserved(self):
        img = torch.full((1, 16, 16, 3), 0.5)
        img[..., 1] = 0.25
        g = torch.Generator().manual_seed(1)
        depth = torch.rand(1, 16, 16, generator=g) * 8 + 1
        radius = torch.rand(1, 16, 16, generator=g) * 3
        out = composite_layers(img, depth, radius, 4, 3.0)
        self.assertTrue(torch.allclose(out, img, atol=1e-4))


class SharpEdgeOutlineTest(unittest.TestCase):
    """No dark outline where a sharp subject meets a blurred far background.

    Mid-grey subject (0.3) at focus (2 m) in columns 0..31, bright background
    (0.9) at 20 m from column 32 with a 12 px CoC radius, 8 layers.
    """

    SUBJECT, BACKGROUND, FOCUS_M = 0.3, 0.9, 2.0

    def _frame(self):
        img = torch.full((1, 64, 64, 3), self.BACKGROUND)
        img[:, :, :32] = self.SUBJECT
        depth = torch.full((1, 64, 64), 20.0)
        depth[:, :, :32] = self.FOCUS_M
        radius = torch.full((1, 64, 64), 12.0)
        radius[:, :, :32] = 0.0
        return img, depth, radius

    def _check(self, img, out):
        self.assertLessEqual((out[:, :, :32] - img[:, :, :32]).abs().max().item(), 1e-4)
        band = out[:, :, 32:35]
        floor = min(self.SUBJECT, self.BACKGROUND) - 0.01
        self.assertGreaterEqual(band.min().item(), floor)
        self.assertGreaterEqual(band.min().item(), self.BACKGROUND - 0.02)

    def test_crisp_depth_edge(self):
        img, depth, radius = self._frame()
        self._check(img, composite_layers(img, depth, radius, 8, self.FOCUS_M))

    def test_soft_depth_edge(self):
        # Like the DA3 depth in the street test: the subject's last columns
        # read slightly behind focus (0.6 px CoC) and the background next to
        # them is soft (1.8 px). A 0.6 px disc reaches no neighbour, so those
        # columns must stay as they are, and the background must not pick up
        # the subject's grey. Equal-width bins (11.5 px / 8 = 1.44 px) put
        # 0.6 px and 1.8 px in one layer blurred at their mean radius, which
        # brightened the subject's edge and darkened the background beside it.
        img, depth, radius = self._frame()
        depth[:, :, 29:32] = 2.05
        radius[:, :, 29:32] = 0.6
        depth[:, :, 32:34] = 2.5
        radius[:, :, 32:34] = 1.8
        self._check(img, composite_layers(img, depth, radius, 8, self.FOCUS_M))


class CompositeLayersFrameIndependenceTest(unittest.TestCase):
    def test_batch_equals_single_frames(self):
        g = torch.Generator().manual_seed(5)
        img = torch.rand(3, 24, 24, 3, generator=g)
        scale = torch.tensor([2.0, 6.0, 15.0]).reshape(3, 1, 1)
        depth = torch.rand(3, 24, 24, generator=g) * scale + 0.5
        radius = coc_radius_map(depth, 50, 2.8, 3.0, 36, 8)
        batch = composite_layers(img, depth, radius, 4, 3.0)
        self.assertEqual(batch.shape, (3, 24, 24, 3))
        for i in range(3):
            single = composite_layers(img[i:i + 1], depth[i:i + 1], radius[i:i + 1], 4, 3.0)
            self.assertLess((batch[i:i + 1] - single).abs().max().item(), 1e-6)


class CudaMatchesCpuTest(unittest.TestCase):
    @unittest.skipUnless(torch.cuda.is_available(), "needs CUDA")
    def test_coc_and_composite_match_cpu(self):
        cuda = torch.device("cuda")
        g = torch.Generator().manual_seed(0)
        img = torch.rand(2, 24, 24, 3, generator=g)
        depth = torch.rand(2, 24, 24, generator=g) * 7.5 + 0.5
        radius_cpu = coc_radius_map(depth, 50, 2.8, 3.0, 36, 8)
        radius_gpu = coc_radius_map(depth.to(cuda), 50, 2.8, 3.0, 36, 8)
        self.assertEqual(radius_gpu.device.type, "cuda")
        self.assertLess((radius_cpu - radius_gpu.cpu()).abs().max().item(), 1e-4)
        out_cpu = composite_layers(img, depth, radius_cpu, 4, 3.0)
        out_gpu = composite_layers(img.to(cuda), depth.to(cuda), radius_gpu, 4, 3.0)
        self.assertEqual(out_gpu.device.type, "cuda")
        self.assertLess((out_cpu - out_gpu.cpu()).abs().max().item(), 1e-4)
        del radius_gpu, out_gpu
        torch.cuda.empty_cache()


class MaxLayersTest(unittest.TestCase):
    def _scene(self):
        depth = torch.linspace(1.0, 20.0, 16 * 16).reshape(1, 16, 16)
        radius = coc_radius_map(depth, 200, 1.4, 3.0, 8, 12)
        img = torch.rand(1, 16, 16, 3, generator=torch.Generator().manual_seed(5))
        return img, depth, radius

    def _check_range(self, out):
        self.assertTrue(torch.isfinite(out).all().item())
        self.assertGreaterEqual(out.min().item(), 0.0)
        self.assertLessEqual(out.max().item(), 1.0)

    def test_uncapped_uses_many_layers(self):
        img, depth, radius = self._scene()
        stats = {}
        composite_layers(img, depth, radius, 8, 3.0, stats=stats)
        self.assertGreater(stats["layers"], 3)

    def test_cap_three(self):
        img, depth, radius = self._scene()
        stats = {}
        out = composite_layers(img, depth, radius, 8, 3.0, max_layers=3, stats=stats)
        self.assertLessEqual(stats["layers"], 3)
        self._check_range(out)

    def test_cap_two(self):
        img, depth, radius = self._scene()
        stats = {}
        out = composite_layers(img, depth, radius, 8, 3.0, max_layers=2, stats=stats)
        self.assertLessEqual(stats["layers"], 2)
        self._check_range(out)

    def test_cap_one(self):
        img, depth, radius = self._scene()
        stats = {}
        out = composite_layers(img, depth, radius, 8, 3.0, max_layers=1, stats=stats)
        self.assertEqual(stats["layers"], 1)
        self._check_range(out)

    def test_large_cap_matches_uncapped(self):
        img, depth, radius = self._scene()
        ref = composite_layers(img, depth, radius, 8, 3.0)
        out = composite_layers(img, depth, radius, 8, 3.0, max_layers=1000)
        self.assertEqual(torch.equal(out, ref), True)


class CocRadiusMapManyDepthsTest(unittest.TestCase):
    @staticmethod
    def _expected(d):
        return min(abs(2500 / (1.8 * 1950) * (d - 2.0) / d) * 32 / 36 / 2, 24)

    def test_many_distinct_depths_match_hand_formula(self):
        values = torch.linspace(0.6, 9.0, 512)
        depth = values.reshape(1, 16, 32)
        out = coc_radius_map(depth, 50.0, 1.8, 2.0, 36.0, 24)
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(out.shape, depth.shape)
        self.assertTrue(bool(torch.isfinite(out).all()))
        self.assertLessEqual(float(out.max()), 24)
        for index in (0, 100, 255, 300, 400, 511):
            d = float(values[index])
            self.assertAlmostEqual(float(out.reshape(-1)[index]), self._expected(d), delta=1e-3)

    def test_depth_exactly_at_focus_gives_zero_radius(self):
        depth = torch.linspace(0.6, 9.0, 512).reshape(1, 16, 32)
        depth[0, 3, 5] = 2.0
        out = coc_radius_map(depth, 50.0, 1.8, 2.0, 36.0, 24)
        self.assertAlmostEqual(float(out[0, 3, 5]), 0.0, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
