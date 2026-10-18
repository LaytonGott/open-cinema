import math
import unittest

from open_optics.coc import coc_for_sensor_obj
from open_optics.lens import Lens
from open_optics.sensor import Sensor
from open_optics.summary import _fmt, shot_summary
from open_optics.vignetting import combined_vignette


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


class TestShotSummaryDof(unittest.TestCase):
    def setUp(self):
        self.sensor = Sensor(36, 24)
        self.lens = Lens(50, 2, 22)

    def test_hyperfocal_line(self):
        coc = coc_for_sensor_obj(self.sensor, standard=1500, squeeze=self.lens.squeeze)
        expected = (50 * 50 / (2 * coc) + 50) / 1000
        text = shot_summary(self.sensor, self.lens, 2, 3)
        self.assertIn(f"Hyperfocal: {expected:.2f} m", text)

    def test_far_limit_infinite_beyond_hyperfocal(self):
        text = shot_summary(self.sensor, self.lens, 2, 100)
        self.assertIn("Far limit: inf m", text)

    def test_limit_lines_order(self):
        lines = shot_summary(self.sensor, self.lens, 2, 3).split("\n")
        self.assertTrue(lines[8].startswith("Near limit:"))
        self.assertTrue(lines[9].startswith("Far limit:"))
        self.assertTrue(lines[10].startswith("Hyperfocal:"))


class TestShotSummaryCorner(unittest.TestCase):
    def setUp(self):
        self.sensor = Sensor(36, 24)
        self.lens = Lens(50, 2, 22)

    def test_corner_line(self):
        text = shot_summary(self.sensor, self.lens, 2.8, 3)
        line = [x for x in text.split("\n") if x.startswith("Corner brightness:")]
        self.assertEqual(len(line), 1)
        fraction = float(line[0].split()[2])
        expected = combined_vignette(
            50, 18, 12, math.hypot(36, 24) / 2, 2.8, self.lens.f_number_min
        )
        self.assertAlmostEqual(fraction, expected, delta=0.01)
        self.assertLessEqual(fraction, 1.0)


class TestShotSummaryOverall(unittest.TestCase):
    def setUp(self):
        self.sensor = Sensor(36, 24)
        self.lens = Lens(50, 1.8, 22)

    def test_finite_far_limit(self):
        # 2*atan(18/50) = 39.60 deg; hyperfocal is about 31 m, so far limit is finite
        text = shot_summary(self.sensor, self.lens, 2.8, 3.0)
        self.assertIn("39.60", text)
        for token in ("mm", "m", "deg"):
            self.assertIn(token, text)
        self.assertNotIn("inf", text)

    def test_deterministic(self):
        self.assertEqual(
            shot_summary(self.sensor, self.lens, 2.8, 3.0),
            shot_summary(self.sensor, self.lens, 2.8, 3.0),
        )

    def test_far_limit_infinite(self):
        text = shot_summary(self.sensor, self.lens, 2.8, 100.0)
        self.assertIn("inf", text)

    def test_bad_focus(self):
        for bad in (0, -1.0):
            with self.assertRaises(ValueError):
                shot_summary(self.sensor, self.lens, 2.8, bad)


if __name__ == "__main__":
    unittest.main()
