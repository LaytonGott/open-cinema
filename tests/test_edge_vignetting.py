import unittest

from open_optics.vignetting import natural_vignette


class NaturalVignetteEdgeTests(unittest.TestCase):
    def test_zero_offset_is_one(self):
        self.assertAlmostEqual(natural_vignette(24, 0), 1.0, places=12)

    def test_corner_offset_hand_value(self):
        # atan(21.63 / 24) ~ 42 deg, cos = 0.7428, cos^4 = 0.3045
        self.assertAlmostEqual(natural_vignette(24, 21.63), 0.3045, delta=0.002)

    def test_differs_from_cos_cubed(self):
        # cos^3 = 0.7428 ** 3 = 0.410, so a cube-law bug would fail here.
        self.assertGreater(abs(natural_vignette(24, 21.63) - 0.7428**3), 0.05)


if __name__ == "__main__":
    unittest.main()
