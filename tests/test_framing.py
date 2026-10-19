import unittest

from open_optics.framing import sensor_height_mm, subject_distance_m


class TestFraming(unittest.TestCase):
    def test_sensor_height_mm_known_value(self):
        # 36 mm * 704 / 1280 = 19.8 mm
        self.assertAlmostEqual(sensor_height_mm(36.0, 1280, 704), 19.8, places=6)

    def test_sensor_height_mm_rejects_zero_width(self):
        with self.assertRaisesRegex(ValueError, "image_width_px"):
            sensor_height_mm(36.0, 0, 704)

    def test_subject_distance_m_known_value(self):
        # h = 24 * 600 / 1200 = 12 mm; u = 50 * (1 + 1700 / 12) / 1000
        self.assertAlmostEqual(subject_distance_m(50, 24, 600, 1200), 7.133333, places=6)

    def test_subject_distance_m_keyword_arguments(self):
        value = subject_distance_m(
            focal_mm=50, sensor_height_mm=24, subject_height_px=600,
            image_height_px=1200, real_height_m=1.7,
        )
        self.assertAlmostEqual(value, 7.133333, places=6)


if __name__ == "__main__":
    unittest.main()
