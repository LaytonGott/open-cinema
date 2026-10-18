import math
import unittest

from open_optics.coc import coc_for_sensor, coc_for_sensor_obj
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


if __name__ == "__main__":
    unittest.main()
