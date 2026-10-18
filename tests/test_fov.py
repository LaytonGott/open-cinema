import unittest

from open_optics.fov import FieldOfView, field_of_view


class FieldOfViewTest(unittest.TestCase):
    def test_full_frame_50mm(self):
        # Published figures for 50 mm on 36x24: 39.6, 27.0 and 46.8 degrees.
        fov = field_of_view(50, 36, 24)
        self.assertIsInstance(fov, FieldOfView)
        self.assertAlmostEqual(fov.hfov_deg, 39.598, delta=0.01)
        self.assertAlmostEqual(fov.vfov_deg, 26.991, delta=0.01)
        self.assertAlmostEqual(fov.dfov_deg, 46.793, delta=0.01)
        self.assertAlmostEqual(fov.crop_factor, 1.0, delta=0.001)
        self.assertAlmostEqual(fov.equiv_focal_ff_mm, 50.0, delta=0.05)

    def test_squeeze_widens_horizontal_only(self):
        # 2x squeeze on 18x24 mm: effective width 36 mm, 2*atan(18/50) = 39.598.
        fov = field_of_view(50, 18, 24, squeeze=2.0)
        self.assertAlmostEqual(fov.hfov_deg, 39.598, delta=0.01)
        self.assertAlmostEqual(fov.vfov_deg, 26.991, delta=0.01)

    def test_crop_factor_super35(self):
        # Diagonal hypot(24.89, 18.66) = 31.10 mm; 43.2666 / 31.10 = 1.391.
        fov = field_of_view(35, 24.89, 18.66)
        self.assertAlmostEqual(fov.crop_factor, 1.391, delta=0.002)
        self.assertAlmostEqual(fov.equiv_focal_ff_mm, 35 * 1.391, delta=0.1)

    def test_validation(self):
        with self.assertRaises(ValueError):
            field_of_view(0, 36, 24)
        with self.assertRaises(TypeError):
            field_of_view(50, 36, 24, squeeze="2")


if __name__ == "__main__":
    unittest.main()
