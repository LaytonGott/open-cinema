import math
import unittest

from open_optics.breathing import breathing_scale, focus_magnification


class TestFocusMagnification(unittest.TestCase):
    def test_50mm_at_1m(self):
        # 1000 / 950 = 1.05263
        self.assertAlmostEqual(focus_magnification(50, 1000), 1.05263, places=4)

    def test_85mm_at_500mm(self):
        # 500 / 415 = 1.20482
        self.assertAlmostEqual(focus_magnification(85, 500), 1.20482, places=4)

    def test_infinity(self):
        self.assertEqual(focus_magnification(50, math.inf), 1.0)

    def test_focus_at_focal_length_raises(self):
        with self.assertRaises(ValueError):
            focus_magnification(50, 50)

    def test_focus_inside_focal_length_raises(self):
        with self.assertRaises(ValueError):
            focus_magnification(50, 40)


class TestBreathingScale(unittest.TestCase):
    def test_strength_zero_is_one(self):
        for d in (100, 500, 1000, 5000, math.inf):
            self.assertEqual(breathing_scale(50, d, 2000, strength=0), 1.0)

    def test_reference_focus_is_one(self):
        self.assertAlmostEqual(breathing_scale(50, 1000, 1000), 1.0, places=9)

    def test_full_strength_is_ratio(self):
        # 1.05263 / 1.02564 = 1.02632
        self.assertAlmostEqual(breathing_scale(50, 1000, 2000, 1.0), 1.02632, places=4)

    def test_strength_out_of_range_raises(self):
        for s in (-0.1, 1.1):
            with self.assertRaises(ValueError):
                breathing_scale(50, 1000, 2000, strength=s)


if __name__ == "__main__":
    unittest.main()
