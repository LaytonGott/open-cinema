import unittest

from open_optics.presets import (
    SENSOR_PRESETS,
    SQUEEZE_PRESETS,
    get_sensor,
    get_squeeze,
    sensor_names,
    squeeze_names,
)


class TestPresets(unittest.TestCase):
    def test_super_35_size(self):
        s = get_sensor("Super 35")
        self.assertAlmostEqual(s.width_mm, 24.89, delta=1e-9)
        self.assertAlmostEqual(s.height_mm, 18.66, delta=1e-9)

    def test_case_and_whitespace_insensitive(self):
        self.assertEqual(get_sensor("full frame"), get_sensor("FULL FRAME"))
        self.assertEqual(get_sensor("  Full Frame "), get_sensor("full frame"))

    def test_unknown_lists_names(self):
        with self.assertRaises(ValueError) as cm:
            get_sensor("nonsense")
        self.assertIn("full frame", str(cm.exception))
        self.assertIn("super 35", str(cm.exception))

    def test_non_str_raises_type_error(self):
        with self.assertRaises(TypeError):
            get_sensor(35)

    def test_sensor_names_sorted(self):
        names = sensor_names()
        self.assertEqual(names, sorted(names))
        self.assertEqual(set(names), set(SENSOR_PRESETS))
        self.assertEqual(len(names), 6)

    def test_full_frame_size(self):
        s = get_sensor("full frame")
        self.assertAlmostEqual(s.width_mm, 36.0, delta=1e-9)
        self.assertAlmostEqual(s.height_mm, 24.0, delta=1e-9)


class TestSqueezePresets(unittest.TestCase):
    def test_2x_case_insensitive(self):
        self.assertAlmostEqual(get_squeeze("2X"), 2.0, delta=1e-12)

    def test_spherical(self):
        self.assertAlmostEqual(get_squeeze("spherical"), 1.0, delta=1e-12)

    def test_unknown_lists_names(self):
        with self.assertRaises(ValueError) as cm:
            get_squeeze("nonsense")
        self.assertIn("1.33x", str(cm.exception))

    def test_squeeze_names_sorted(self):
        names = squeeze_names()
        self.assertEqual(names, sorted(names))
        self.assertEqual(set(names), set(SQUEEZE_PRESETS))
        self.assertEqual(len(names), 5)


if __name__ == "__main__":
    unittest.main()
