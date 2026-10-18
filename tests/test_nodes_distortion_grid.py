import unittest

import torch

from open_optics import distortion, pixels
from open_optics.lens import Lens
from open_optics.sensor import Sensor
from open_optics_nodes.distortion_grid import (
    build_source_grid, crop_zoom, sample_bilinear)


class TestBuildSourceGrid(unittest.TestCase):
    def test_zero_coefficients_identity(self):
        for direction in ("remove", "apply"):
            grid = build_source_grid(5, 4, 35.0, 36.0, 0, 0, 0, 0, 0, direction)
            self.assertEqual(len(grid), 4)
            for v in range(4):
                self.assertEqual(len(grid[v]), 5)
                for u in range(5):
                    self.assertAlmostEqual(grid[v][u][0], u, places=6)
                    self.assertAlmostEqual(grid[v][u][1], v, places=6)

    def test_remove_matches_distort_pixel(self):
        grid = build_source_grid(9, 9, 35.0, 36.0, 0.1, 0, 0, 0, 0, "remove")
        ex, ey = distortion.distort_pixel(8, 4, Sensor(36, 24), Lens(35, 2.8, 22),
                                          9, 9, k1=0.1)
        self.assertAlmostEqual(grid[4][8][0], ex, places=6)
        self.assertAlmostEqual(grid[4][8][1], ey, places=6)

    def test_apply_matches_undistort_pixel(self):
        grid = build_source_grid(9, 9, 35.0, 36.0, 0.1, 0, 0, 0, 0, "apply")
        ex, ey = distortion.undistort_pixel(8, 4, Sensor(36, 24), Lens(35, 2.8, 22),
                                            9, 9, k1=0.1)
        self.assertAlmostEqual(grid[4][8][0], ex, places=6)
        self.assertAlmostEqual(grid[4][8][1], ey, places=6)

    def test_bad_direction(self):
        with self.assertRaises(ValueError):
            build_source_grid(5, 4, 35.0, 36.0, 0, 0, 0, 0, 0, "bad")


class TestApplyZoom(unittest.TestCase):
    def test_default_zoom_is_one(self):
        default = build_source_grid(32, 24, 35.0, 36.0, -0.2, 0, 0, 0, 0, "apply")
        explicit = build_source_grid(32, 24, 35.0, 36.0, -0.2, 0, 0, 0, 0,
                                     "apply", zoom=1.0)
        for v in range(24):
            for u in range(32):
                self.assertEqual(default[v][u], explicit[v][u])

    def test_zoom_two_matches_hand_chain(self):
        grid = build_source_grid(32, 24, 35.0, 36.0, -0.2, 0, 0, 0, 0,
                                 "apply", zoom=2.0)
        x, y = pixels.pixel_to_lens(7, 5, 32, 24, 36, 35)
        x, y = distortion.undistort_point(x / 2, y / 2, -0.2, 0, 0, 0, 0)
        ex, ey = pixels.lens_to_pixel(x, y, 32, 24, 36, 35)
        self.assertAlmostEqual(grid[5][7][0], ex, places=9)
        self.assertAlmostEqual(grid[5][7][1], ey, places=9)


class TestCropZoom(unittest.TestCase):
    def test_zero_coefficients(self):
        self.assertEqual(crop_zoom(32, 24, 35.0, 36.0, 0, 0, 0, 0, 0), 1.0)

    def test_border_free(self):
        zoom = crop_zoom(32, 24, 35.0, 36.0, 0.2, 0, 0, 0, 0)
        self.assertGreater(zoom, 1.0)
        grid = build_source_grid(32, 24, 35.0, 36.0, 0.2, 0, 0, 0, 0,
                                 "remove", zoom=zoom)
        for row in grid:
            for sx, sy in row:
                self.assertTrue(-1e-6 <= sx <= 31 + 1e-6)
                self.assertTrue(-1e-6 <= sy <= 23 + 1e-6)


class TestSampleBilinear(unittest.TestCase):
    def setUp(self):
        gen = torch.Generator().manual_seed(0)
        self.image = torch.rand(1, 6, 7, 3, generator=gen)
        v, u = torch.meshgrid(torch.arange(6.0), torch.arange(7.0), indexing="ij")
        self.u, self.v = u, v

    def test_identity(self):
        grid = torch.stack([self.u, self.v], dim=-1)
        out = sample_bilinear(self.image, grid)
        self.assertEqual(out.dtype, torch.float32)
        self.assertTrue(torch.allclose(out, self.image, atol=1e-5))

    def test_half_pixel_shift(self):
        grid = torch.stack([self.u + 0.5, self.v], dim=-1)
        out = sample_bilinear(self.image, grid)
        expected = (self.image[0, :, 2] + self.image[0, :, 3]) / 2
        self.assertTrue(torch.allclose(out[0, :, 2], expected, atol=1e-5))

    def test_border_clamp(self):
        grid = torch.stack([torch.full_like(self.u, -5.0), self.v], dim=-1)
        out = sample_bilinear(self.image, grid)
        expected = self.image[:, :, 0:1, :].expand(-1, -1, 7, -1)
        self.assertTrue(torch.allclose(out, expected, atol=1e-5))

    def test_black_outside_zeroes_out_of_range(self):
        grid = torch.stack([torch.full_like(self.u, -5.0), self.v], dim=-1)
        out = sample_bilinear(self.image, grid, outside="black")
        self.assertTrue(torch.equal(out, torch.zeros_like(out)))
        ident = torch.stack([self.u, self.v], dim=-1)
        out = sample_bilinear(self.image, ident, outside="black")
        self.assertTrue(torch.allclose(out, self.image, atol=1e-5))

    def test_bad_outside_raises(self):
        grid = torch.stack([self.u, self.v], dim=-1)
        with self.assertRaisesRegex(ValueError, "outside"):
            sample_bilinear(self.image, grid, outside="wrap")


if __name__ == "__main__":
    unittest.main()
