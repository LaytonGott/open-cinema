import math
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


class TestVignetteWhiteImage(unittest.TestCase):
    def setUp(self):
        self.img = torch.ones((1, 64, 64, 3), dtype=torch.float32)
        self.node = OpenOptics_Vignette()
        # Pixel pitch 36/64 mm, centre at 63/2 pixels: corner offset is 31.5 pixels.
        d = 31.5 * 36.0 / 64.0
        r = math.hypot(d, d)
        self.gain = math.cos(math.atan(r / 35.0)) ** 4

    def test_linear_corners(self):
        out = self.node.apply(self.img, 35.0, 36.0, 1.0, "linear")[0]
        self.assertAlmostEqual(out[0, 0, 0, 0].item(), self.gain, delta=1e-4)
        self.assertAlmostEqual(out[0, 63, 63, 1].item(), self.gain, delta=1e-4)
        c = [out[0, 0, 0, 0], out[0, 0, 63, 0], out[0, 63, 0, 0], out[0, 63, 63, 0]]
        for v in c:
            self.assertAlmostEqual(v.item(), c[0].item(), delta=1e-6)

    def test_srgb_corner(self):
        out = self.node.apply(self.img, 35.0, 36.0, 1.0, "srgb")[0]
        expected = 1.055 * self.gain ** (1 / 2.4) - 0.055
        self.assertAlmostEqual(out[0, 0, 0, 0].item(), expected, delta=1e-4)

    def test_centre_and_diagonal(self):
        out = self.node.apply(self.img, 35.0, 36.0, 1.0, "linear")[0]
        self.assertAlmostEqual(out[0, 31, 31, 0].item(), 1.0, delta=0.01)
        self.assertAlmostEqual(out[0, 32, 32, 0].item(), 1.0, delta=0.01)
        diag = [out[0, i, i, 0].item() for i in range(32, 64)]
        for a, b in zip(diag, diag[1:]):
            self.assertGreaterEqual(a, b)


class TestVignetteStrength(unittest.TestCase):
    def setUp(self):
        self.img = torch.full((1, 32, 32, 3), 0.8, dtype=torch.float32)
        self.node = OpenOptics_Vignette()

    def corner(self, strength):
        out = self.node.apply(self.img, 35.0, 36.0, strength, "linear")[0]
        return out[0, 0, 0, 0].item()

    def test_strength_zero_srgb_identity(self):
        out = self.node.apply(self.img, 35.0, 36.0, 0.0, "srgb")[0]
        self.assertTrue(torch.allclose(out, self.img, atol=1e-5))

    def test_half_strength_corner(self):
        g = vignetting.natural_vignette_px(35.0, 0, 0, 36.0, 32, 32)
        self.assertAlmostEqual(self.corner(0.5), 0.8 * (1 - 0.5 * (1 - g)), delta=1e-5)

    def test_half_strength_between(self):
        c0, c5, c1 = self.corner(0.0), self.corner(0.5), self.corner(1.0)
        self.assertLess(c1, c5)
        self.assertLess(c5, c0)

    def test_output_properties(self):
        out = self.node.apply(self.img, 35.0, 36.0, 0.5, "linear")[0]
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(out.shape, self.img.shape)
        self.assertTrue(torch.isfinite(out).all().item())
        self.assertGreaterEqual(out.min().item(), 0.0)
        self.assertLessEqual(out.max().item(), 1.0)


class VignetteAcrossLensesTest(unittest.TestCase):
    def setUp(self):
        self.img = torch.ones(1, 17, 25, 3, dtype=torch.float32)
        self.node = OpenOptics_Vignette()

    def run_lens(self, focal_mm):
        return self.node.apply(self.img, focal_mm, 36.0, 1.0, "linear")[0]

    def test_wide_lens_darker_corner(self):
        wide = self.run_lens(14)
        tele = self.run_lens(50)
        self.assertLess(wide[0, 0, 0, 0].item(), tele[0, 0, 0, 0].item())
        for out in (wide, tele):
            self.assertGreaterEqual(out.min().item(), 0.0)
            self.assertLessEqual(out.max().item(), 1.0)

    def test_gain_symmetric_and_bounded(self):
        out = self.run_lens(14)
        self.assertTrue(torch.allclose(out, out.flip(1), atol=1e-6))
        self.assertTrue(torch.allclose(out, out.flip(2), atol=1e-6))


class VignetteChunkTest(unittest.TestCase):
    def setUp(self):
        g = torch.Generator().manual_seed(3)
        self.img = torch.rand(5, 16, 16, 3, generator=g)
        self.node = OpenOptics_Vignette()

    def test_input_types_lists_chunk_frames(self):
        spec = OpenOptics_Vignette.INPUT_TYPES()["required"]["chunk_frames"]
        self.assertEqual(spec[0], "INT")
        self.assertEqual(spec[1]["default"], 8)
        self.assertEqual(spec[1]["min"], 1)

    def test_chunk_frames_zero_raises(self):
        with self.assertRaises(ValueError) as cm:
            self.node.apply(self.img, chunk_frames=0)
        self.assertIn("chunk_frames", str(cm.exception))

    def test_chunks_equal_full_batch(self):
        full = self.node.apply(self.img, chunk_frames=5)[0]
        for n in (1, 3):
            out = self.node.apply(self.img, chunk_frames=n)[0]
            self.assertEqual(out.shape, full.shape)
            self.assertLess((out - full).abs().max().item(), 1e-5)

    def test_output_cpu_and_input_unchanged(self):
        before = self.img.clone()
        out = self.node.apply(self.img, chunk_frames=2)[0]
        self.assertEqual(out.device.type, "cpu")
        self.assertEqual(out.dtype, torch.float32)
        self.assertTrue(torch.equal(self.img, before))


if __name__ == "__main__":
    unittest.main()
