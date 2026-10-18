import math
import unittest

from open_optics.coc import blur_diameter_mm, coc_for_sensor, coc_for_sensor_obj
from open_optics.sensor import Sensor


class TestCocForSensor(unittest.TestCase):
    def test_full_frame(self):
        # hypot(36, 24) = 43.2666 mm; / 1500 = 0.028844 mm
        self.assertAlmostEqual(coc_for_sensor(36, 24), 0.028844, places=5)

    def test_zeiss_standard(self):
        # 43.2666 / 1730 = 0.025010 mm
        self.assertAlmostEqual(coc_for_sensor(36, 24, standard=1730), 0.025010, places=5)

    def test_user_value(self):
        self.assertEqual(coc_for_sensor(36, 24, user_value_mm=0.03), 0.03)

    def test_negative_user_value(self):
        with self.assertRaises(ValueError):
            coc_for_sensor(36, 24, user_value_mm=-0.01)

    def test_bad_standard(self):
        with self.assertRaises(ValueError):
            coc_for_sensor(36, 24, standard=1000)

    def test_squeeze(self):
        self.assertAlmostEqual(
            coc_for_sensor(18, 24, squeeze=2.0), math.hypot(36, 24) / 1500, places=6
        )


class TestCocForSensorObj(unittest.TestCase):
    def test_computed(self):
        # hypot(36, 24) / 1500 = 0.028844 mm
        self.assertAlmostEqual(coc_for_sensor_obj(Sensor(36, 24)), 0.028844, places=5)

    def test_override(self):
        self.assertEqual(coc_for_sensor_obj(Sensor(36, 24, coc_mm=0.03)), 0.03)


class TestBlurDiameterMm(unittest.TestCase):
    # 50 mm f/2.8 focused at 3000 mm: 2500 / (2.8 * 2950) mm for an infinite subject
    INF_VALUE = 2500 / (2.8 * 2950)

    def test_infinity_subject(self):
        self.assertAlmostEqual(
            blur_diameter_mm(50, 2.8, 3000, math.inf), 0.30266, places=4
        )

    def test_in_focus_is_zero(self):
        self.assertEqual(blur_diameter_mm(50, 2.8, 3000, 3000), 0)

    def test_near_subject_negative(self):
        value = blur_diameter_mm(50, 2.8, 3000, 1500)
        self.assertLess(value, 0)
        self.assertAlmostEqual(abs(value), self.INF_VALUE, places=6)

    def test_far_subject_positive_half(self):
        value = blur_diameter_mm(50, 2.8, 3000, 6000)
        self.assertGreater(value, 0)
        self.assertAlmostEqual(value, self.INF_VALUE / 2, places=6)

    def test_focus_not_beyond_focal_raises(self):
        for focus in (50, 40):
            with self.assertRaises(ValueError):
                blur_diameter_mm(50, 2.8, focus, math.inf)

    def test_zero_subject_raises(self):
        with self.assertRaises(ValueError):
            blur_diameter_mm(50, 2.8, 3000, 0)


if __name__ == "__main__":
    unittest.main()
