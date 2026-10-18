import unittest

import torch

from open_optics import vignetting
from open_optics_nodes.vignette import OpenOptics_Vignette


class TestVignetteNode(unittest.TestCase):
    def setUp(self):
        self.img = torch.full((1, 15, 15, 3), 0.5, dtype=torch.float32)
        self.node = OpenOptics_Vignette()

    def test_centre_unchanged(self):
        out = self.node.apply(self.img, colorspace="linear")[0]
        self.assertAlmostEqual(out[0, 7, 7, 0].item(), 0.5, places=6)

    def test_corner_matches_library(self):
        out = self.node.apply(self.img, 35.0, 36.0, 1.0, "linear")[0]
        gain = vignetting.natural_vignette_px(35.0, 0, 0, 36.0, 15, 15)
        self.assertLess(gain, 1.0)
        self.assertAlmostEqual(out[0, 0, 0, 1].item(), 0.5 * gain, places=5)

    def test_srgb_corner_is_physically_scaled(self):
        g = vignetting.natural_vignette_px(35.0, 0, 0, 36.0, 15, 15)
        v = 0.5
        lin = ((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92
        lin *= g
        expected = 1.055 * lin ** (1 / 2.4) - 0.055 if lin > 0.0031308 else 12.92 * lin
        out = self.node.apply(self.img, 35.0, 36.0, 1.0, "srgb")[0]
        self.assertAlmostEqual(out[0, 0, 0, 0].item(), expected, delta=1e-4)
        self.assertGreater(out[0, 0, 0, 0].item(), 0.5 * g)

    def test_linear_corner_is_direct_product(self):
        g = vignetting.natural_vignette_px(35.0, 0, 0, 36.0, 15, 15)
        out = self.node.apply(self.img, 35.0, 36.0, 1.0, "linear")[0]
        self.assertAlmostEqual(out[0, 0, 0, 0].item(), 0.5 * g, places=6)
        self.assertAlmostEqual(out[0, 7, 7, 0].item(), 0.5, places=6)

    def test_strength_zero_identity(self):
        out = self.node.apply(self.img, strength=0.0, colorspace="linear")[0]
        self.assertTrue(torch.allclose(out, self.img, atol=1e-6))

    def test_focal_zero_names_input(self):
        with self.assertRaises(ValueError) as cm:
            self.node.apply(self.img, focal_mm=0)
        self.assertIn("focal_mm", str(cm.exception))

    def test_negative_sensor_width_names_input(self):
        with self.assertRaises(ValueError) as cm:
            self.node.apply(self.img, sensor_width_mm=-1)
        self.assertIn("sensor_width_mm", str(cm.exception))

    def test_strength_out_of_range_names_input(self):
        with self.assertRaises(ValueError) as cm:
            self.node.apply(self.img, strength=2)
        self.assertIn("strength", str(cm.exception))
        self.assertIn("2", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
