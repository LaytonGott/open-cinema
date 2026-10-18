import json
import unittest

from open_optics.lens import Lens


class TestLens(unittest.TestCase):
    def test_default_squeeze(self):
        self.assertAlmostEqual(Lens(50, 1.8, 16).squeeze, 1.0, places=6)

    def test_construction(self):
        lens = Lens(50, 1.8, 16)
        self.assertAlmostEqual(lens.focal_mm, 50, places=6)
        self.assertAlmostEqual(lens.f_number_min, 1.8, places=6)
        self.assertAlmostEqual(lens.f_number_max, 16, places=6)

    def test_zero_focal_refused(self):
        with self.assertRaises(ValueError):
            Lens(0, 1.8, 16)

    def test_reversed_f_numbers_refused(self):
        with self.assertRaises(ValueError):
            Lens(50, 22, 2)

    def test_json_round_trip_squeeze(self):
        lens = Lens(50, 1.8, 16, squeeze=2.0)
        self.assertEqual(Lens.from_dict(json.loads(json.dumps(lens.to_dict()))), lens)

    def test_json_round_trip_default(self):
        lens = Lens(35, 2, 22)
        restored = Lens.from_dict(json.loads(json.dumps(lens.to_dict())))
        self.assertEqual(restored, lens)
        self.assertAlmostEqual(restored.squeeze, 1.0, places=6)

    def test_from_dict_squeeze_absent(self):
        lens = Lens.from_dict({"focal_mm": 50, "f_number_min": 1.8, "f_number_max": 16})
        self.assertAlmostEqual(lens.squeeze, 1.0, places=6)

    def test_from_dict_missing_focal_refused(self):
        with self.assertRaisesRegex(ValueError, "focal_mm"):
            Lens.from_dict({"f_number_min": 1.8, "f_number_max": 16})


if __name__ == "__main__":
    unittest.main()
