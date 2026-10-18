import unittest

from open_optics.pixels import focal_length_px, lens_to_pixel, pixel_to_lens

ARGS = (1920, 1080, 36, 50)


class TestPixels(unittest.TestCase):
    def test_focal_length_px(self):
        self.assertAlmostEqual(focal_length_px(50, 36, 1920), 2666.6667, places=3)

    def test_centre_maps_to_zero(self):
        x, y = pixel_to_lens(959.5, 539.5, *ARGS)
        self.assertAlmostEqual(x, 0, places=9)
        self.assertAlmostEqual(y, 0, places=9)

    def test_right_edge_value(self):
        x, y = pixel_to_lens(1919, 539.5, *ARGS)
        self.assertAlmostEqual(x, 0.359813, places=6)
        self.assertAlmostEqual(y, 0, places=9)

    def test_custom_principal_point(self):
        x, y = pixel_to_lens(100, 200, *ARGS, cx=100, cy=200)
        self.assertAlmostEqual(x, 0, places=9)
        self.assertAlmostEqual(y, 0, places=9)

    def test_round_trip(self):
        for px, py in [(0, 0), (1919, 1079), (123.25, 456.75), (959.5, 539.5)]:
            lx, ly = pixel_to_lens(px, py, *ARGS)
            rx, ry = lens_to_pixel(lx, ly, *ARGS)
            self.assertAlmostEqual(rx, px, places=9)
            self.assertAlmostEqual(ry, py, places=9)

    def test_invalid_width(self):
        with self.assertRaises(ValueError):
            pixel_to_lens(10, 10, 0, 1080, 36, 50)


if __name__ == "__main__":
    unittest.main()
