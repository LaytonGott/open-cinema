import math
import unittest

from open_optics.fov import FieldOfView, angle_of_view, field_of_view, focal_from_angle, sensor_angles
from open_optics.sensor import Sensor


class AngleOfViewTest(unittest.TestCase):
    def test_50mm_values(self):
        # 2*atan(36/100) = 39.598; 2*atan(24/100) = 26.991; 2*atan(43.2666/100) = 46.793.
        self.assertAlmostEqual(angle_of_view(50, 36), 39.598, delta=0.001)
        self.assertAlmostEqual(angle_of_view(50, 24), 26.991, delta=0.001)
        self.assertAlmostEqual(angle_of_view(50, 43.2666), 46.793, delta=0.001)

    def test_extremes(self):
        long = angle_of_view(10000, 36)
        self.assertGreater(long, 0)
        self.assertLess(long, 1)
        self.assertLess(angle_of_view(1, 36), 180)

    def test_zero_focal_raises(self):
        with self.assertRaises(ValueError):
            angle_of_view(0, 36)


class SensorAnglesTest(unittest.TestCase):
    def test_50mm_on_36x24(self):
        # 2*atan(36/100), 2*atan(24/100), 2*atan(43.2666/100) in degrees.
        h, v, d = sensor_angles(50, Sensor(36, 24))
        self.assertAlmostEqual(h, 39.598, delta=0.001)
        self.assertAlmostEqual(v, 26.991, delta=0.001)
        self.assertAlmostEqual(d, 46.793, delta=0.001)


class FocalFromAngleTest(unittest.TestCase):
    def test_known_value(self):
        # 36 / (2*tan(19.799 deg)) = 36 / 0.72 = 50 mm.
        self.assertAlmostEqual(focal_from_angle(39.598, 36), 50.0, delta=0.01)

    def test_round_trip(self):
        for focal in (35, 85, 200):
            back = focal_from_angle(angle_of_view(focal, 36), 36)
            self.assertLess(abs(back - focal) / focal, 1e-9)

    def test_angle_out_of_range_raises(self):
        for bad in (180, 0, -5):
            with self.assertRaises(ValueError):
                focal_from_angle(bad, 36)


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


class AnamorphicSqueezeTest(unittest.TestCase):
    # 22 x 12.37 mm gate, 50 mm lens.
    def test_hfov_values(self):
        # 2*atan(44/100) = 47.499 deg; 2*atan(22/100) = 24.815 deg.
        self.assertAlmostEqual(field_of_view(50, 22, 12.37, squeeze=2.0).hfov_deg, 47.499, delta=0.001)
        self.assertAlmostEqual(field_of_view(50, 22, 12.37, squeeze=1.0).hfov_deg, 24.815, delta=0.001)

    def test_vfov_unaffected_by_squeeze(self):
        v2 = field_of_view(50, 22, 12.37, squeeze=2.0).vfov_deg
        v1 = field_of_view(50, 22, 12.37, squeeze=1.0).vfov_deg
        self.assertAlmostEqual(v2, v1, places=12)
        self.assertAlmostEqual(v1, math.degrees(2 * math.atan(12.37 / 100)), delta=0.001)

    def test_dfov_squeeze_one(self):
        fov = field_of_view(50, 22, 12.37, squeeze=1.0)
        expected = math.degrees(2 * math.atan(math.hypot(22, 12.37) / 100))
        self.assertAlmostEqual(fov.dfov_deg, expected, delta=0.001)

    def test_equiv_focal_squeeze_two(self):
        fov = field_of_view(50, 22, 12.37, squeeze=2.0)
        self.assertAlmostEqual(fov.equiv_focal_ff_mm, 50 * 43.2666 / math.hypot(44, 12.37), places=6)

    def test_focal_errors(self):
        for bad in (0, -5):
            with self.assertRaises(ValueError) as ctx:
                field_of_view(bad, 22, 12.37)
            self.assertIn("focal_mm", str(ctx.exception))
        with self.assertRaises(TypeError):
            field_of_view("50", 22, 12.37)


if __name__ == "__main__":
    unittest.main()
