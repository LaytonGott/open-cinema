import json
import unittest

from open_optics.sensor import Sensor


class TestSensor(unittest.TestCase):
    def test_full_frame_diagonal(self):
        # sqrt(36^2 + 24^2) = sqrt(1872) = 43.2666
        self.assertAlmostEqual(Sensor(36, 24).diagonal_mm, 43.2666, places=3)

    def test_aspect_ratio(self):
        self.assertAlmostEqual(Sensor(36, 24).aspect_ratio, 1.5, places=6)

    def test_negative_width_refused(self):
        with self.assertRaisesRegex(ValueError, "width_mm"):
            Sensor(-1, 24)

    def test_zero_coc_refused(self):
        with self.assertRaises(ValueError):
            Sensor(36, 24, coc_mm=0)

    def test_optional_fields(self):
        s = Sensor(36, 24, name="FF", coc_mm=0.03)
        self.assertEqual(s.name, "FF")
        self.assertEqual(s.coc_mm, 0.03)

    def test_json_round_trip_named(self):
        s = Sensor(36, 24, name="FF", coc_mm=0.03)
        self.assertEqual(Sensor.from_dict(json.loads(json.dumps(s.to_dict()))), s)

    def test_json_round_trip_plain(self):
        s = Sensor(36, 24)
        self.assertEqual(Sensor.from_dict(json.loads(json.dumps(s.to_dict()))), s)

    def test_from_dict_missing_key(self):
        with self.assertRaisesRegex(ValueError, "height_mm"):
            Sensor.from_dict({"width_mm": 36})

    def test_from_dict_negative_width(self):
        with self.assertRaises(ValueError):
            Sensor.from_dict({"width_mm": -1, "height_mm": 24})


if __name__ == "__main__":
    unittest.main()
