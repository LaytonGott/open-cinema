import unittest

from open_optics.framing import sensor_height_mm


class TestFraming(unittest.TestCase):
    def test_sensor_height_mm_known_value(self):
        # 36 mm * 704 / 1280 = 19.8 mm
        self.assertAlmostEqual(sensor_height_mm(36.0, 1280, 704), 19.8, places=6)

    def test_sensor_height_mm_rejects_zero_width(self):
        with self.assertRaisesRegex(ValueError, "image_width_px"):
            sensor_height_mm(36.0, 0, 704)


if __name__ == "__main__":
    unittest.main()
