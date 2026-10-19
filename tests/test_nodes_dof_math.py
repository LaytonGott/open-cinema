import unittest

import torch

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

    def test_constant_colour_preserved(self):
        img = torch.full((1, 16, 16, 3), 0.5)
        img[..., 1] = 0.25
        g = torch.Generator().manual_seed(1)
        depth = torch.rand(1, 16, 16, generator=g) * 8 + 1
        radius = torch.rand(1, 16, 16, generator=g) * 3
        out = composite_layers(img, depth, radius, 4, 3.0)
        self.assertTrue(torch.allclose(out, img, atol=1e-4))


if __name__ == "__main__":
    unittest.main()
