import unittest

from open_optics.color import apply_vignette_linear, linear_to_srgb, srgb_to_linear


class TestColor(unittest.TestCase):
    def test_round_trip(self):
        for i in range(101):
            v = i / 100
            self.assertAlmostEqual(linear_to_srgb(srgb_to_linear(v)), v, delta=1e-6)

    def test_srgb_to_linear_published_value(self):
        self.assertAlmostEqual(srgb_to_linear(0.5), 0.21404, places=4)

    def test_apply_vignette_linear_half(self):
        # linear 0.21404 * 0.5 = 0.10702, back to sRGB is about 0.3607
        result = apply_vignette_linear(0.5, 0.5)
        self.assertAlmostEqual(result, 0.3607, delta=2e-3)
        self.assertNotAlmostEqual(result, 0.25, delta=0.05)

    def test_apply_vignette_linear_full_brightness(self):
        self.assertAlmostEqual(apply_vignette_linear(0.5, 1.0), 0.5, delta=1e-6)

    def test_out_of_range_raises(self):
        for bad in (-0.1, 1.1):
            with self.assertRaises(ValueError):
                srgb_to_linear(bad)
            with self.assertRaises(ValueError):
                linear_to_srgb(bad)
            with self.assertRaises(ValueError):
                apply_vignette_linear(bad, 0.5)
            with self.assertRaises(ValueError):
                apply_vignette_linear(0.5, bad)


if __name__ == "__main__":
    unittest.main()
