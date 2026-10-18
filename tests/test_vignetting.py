import unittest

from open_optics.vignetting import (
    brightness_to_stops,
    natural_vignette,
    natural_vignette_px,
)


class NaturalVignetteTests(unittest.TestCase):
    def test_24mm_corner(self):
        # r^2 = 18^2 + 12^2 = 468; 1 / (1 + 468/576)^2 = 0.30440
        self.assertAlmostEqual(natural_vignette(24, 18, 12), 0.30440, delta=1e-4)

    def test_24mm_corner_stops(self):
        stops = brightness_to_stops(natural_vignette(24, 18, 12))
        self.assertAlmostEqual(stops, -1.716, delta=1e-3)

    def test_50mm_corner(self):
        # 1 / (1 + 468/2500)^2 = 0.70950
        self.assertAlmostEqual(natural_vignette(50, 18, 12), 0.70950, delta=1e-4)

    def test_centre(self):
        self.assertEqual(natural_vignette(24, 0, 0), 1.0)
        self.assertEqual(brightness_to_stops(natural_vignette(24, 0, 0)), 0.0)

    def test_invalid_focal(self):
        with self.assertRaises(ValueError):
            natural_vignette(0, 1, 1)


class NaturalVignettePxTests(unittest.TestCase):
    def test_corner_pixel(self):
        # Pixel centre sits 0.5 px (0.005 mm) inside the true corner.
        value = natural_vignette_px(24, 0, 0, 36, 3600, 2400)
        self.assertAlmostEqual(value, 0.30440, delta=1e-3)

    def test_centre_pixel(self):
        value = natural_vignette_px(24, 1799.5, 1199.5, 36, 3600, 2400)
        self.assertAlmostEqual(value, 1.0, delta=1e-9)

    def test_invalid_focal(self):
        with self.assertRaises(ValueError):
            natural_vignette_px(0, 0, 0, 36, 3600, 2400)


if __name__ == "__main__":
    unittest.main()
