import unittest

from open_optics.crop import crop_factor


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


if __name__ == "__main__":
    unittest.main()
