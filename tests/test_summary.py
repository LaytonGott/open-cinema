import math
import unittest

from open_optics.lens import Lens
from open_optics.sensor import Sensor
from open_optics.summary import _fmt, shot_summary


class TestFmt(unittest.TestCase):
    def test_two_decimals(self):
        self.assertEqual(_fmt(39.6), "39.60")

    def test_rounds_third(self):
        self.assertEqual(_fmt(1 / 3), "0.33")

    def test_infinity(self):
        self.assertEqual(_fmt(math.inf), "inf")


class TestShotSummaryOptics(unittest.TestCase):
    def setUp(self):
        self.sensor = Sensor(36, 24)
        self.lens = Lens(50, 2, 22)

    def test_fov_lines(self):
        # 2*atan(18/50) = 39.60 deg, 2*atan(12/50) = 26.99 deg
        text = shot_summary(self.sensor, self.lens, 2, 3)
        self.assertIn("Horizontal FOV: 39.60 deg", text)
        self.assertIn("Vertical FOV: 26.99 deg", text)

    def test_first_lines(self):
        lines = shot_summary(self.sensor, self.lens, 2, 3).split("\n")
        self.assertEqual(lines[0], "Focal length: 50.00 mm")
        self.assertEqual(lines[1], "F-number: 2.00")
        self.assertEqual(lines[2], "Focus: 3.00 m")

    def test_zero_focus_raises(self):
        with self.assertRaises(ValueError):
            shot_summary(self.sensor, self.lens, 2, 0)


if __name__ == "__main__":
    unittest.main()
