import math
import unittest

from open_optics.focus_pull import focus_at_frame


class TestFocusAtFrame(unittest.TestCase):
    def test_midpoint_interpolates_diopters(self):
        # 1000 mm = 1 D, 500 mm = 2 D; midpoint 1.5 D = 666.667 mm
        self.assertAlmostEqual(focus_at_frame([(0, 1000), (10, 500)], 5), 2000 / 3, places=6)

    def test_keyframes_and_clamping(self):
        kf = [(0, 1000), (10, 500)]
        self.assertEqual(focus_at_frame(kf, 10), 500)
        self.assertEqual(focus_at_frame(kf, -5), 1000)
        self.assertEqual(focus_at_frame(kf, 20), 500)

    def test_infinity(self):
        kf = [(0, math.inf), (10, 1000)]
        self.assertAlmostEqual(focus_at_frame(kf, 5), 2000, places=6)
        self.assertEqual(focus_at_frame(kf, 0), math.inf)

    def test_errors(self):
        with self.assertRaises(ValueError):
            focus_at_frame([(0, 1000)], 0)
        with self.assertRaises(ValueError):
            focus_at_frame([(10, 1000), (0, 500)], 0)
        with self.assertRaisesRegex(ValueError, "repeated"):
            focus_at_frame([(0, 1000), (0, 500)], 0)


if __name__ == "__main__":
    unittest.main()
