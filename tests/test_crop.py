import unittest

from open_optics.crop import crop_factor, equivalent_f_number, equivalent_focal_mm


class TestCropFactor(unittest.TestCase):
    def test_super35(self):
        # 43.2666 / sqrt(24.89^2 + 18.66^2) = 43.2666 / 31.1075 = 1.3909
        self.assertAlmostEqual(crop_factor(24.89, 18.66), 1.3909, places=3)

    def test_full_frame_is_one(self):
        # sqrt(36^2 + 24^2) = 43.2666 mm, the full-frame diagonal
        self.assertAlmostEqual(crop_factor(36, 24), 1.0, places=4)

    def test_zero_width_raises(self):
        with self.assertRaises(ValueError):
            crop_factor(0, 24)


class TestEquivalent(unittest.TestCase):
    def test_focal_super35(self):
        # 35 * 1.3909 = 48.68
        self.assertAlmostEqual(equivalent_focal_mm(35, 24.89, 18.66), 48.68, delta=0.01)

    def test_f_number_super35(self):
        # 2.8 * 1.3909 = 3.894
        self.assertAlmostEqual(equivalent_f_number(2.8, 24.89, 18.66), 3.894, delta=0.01)

    def test_full_frame_unchanged(self):
        self.assertAlmostEqual(equivalent_focal_mm(50, 36, 24), 50, places=4)
        self.assertAlmostEqual(equivalent_f_number(2.8, 36, 24), 2.8, places=4)

    def test_zero_focal_raises(self):
        with self.assertRaises(ValueError):
            equivalent_focal_mm(0, 24.89, 18.66)

    def test_zero_f_number_raises(self):
        with self.assertRaises(ValueError):
            equivalent_f_number(0, 24.89, 18.66)


if __name__ == "__main__":
    unittest.main()
