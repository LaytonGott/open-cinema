import math
import unittest

from open_optics.focus_pull import focus_at_frame


class TestFocusAtFrame(unittest.TestCase):
    KF = [(0, 3000), (120, 1200)]

    def test_midpoint_interpolates_diopters(self):
        # 1 / (0.5 * (1/3 + 1/1.2)) m = 1.7143 m
        self.assertAlmostEqual(focus_at_frame(self.KF, 60), 1714.3, delta=0.1)

    def test_keyframes_exact(self):
        self.assertEqual(focus_at_frame(self.KF, 0), 3000)
        self.assertEqual(focus_at_frame(self.KF, 120), 1200)

    def test_monotonic_decrease(self):
        values = [focus_at_frame(self.KF, f) for f in range(10, 111, 10)]
        for a, b in zip(values, values[1:]):
            self.assertLess(b, a)

    def test_infinity_to_1000(self):
        kf = [(0, math.inf), (100, 1000)]
        self.assertEqual(focus_at_frame(kf, 0), math.inf)
        # 0 D to 1 D, midpoint 0.5 D = 2000 mm
        self.assertAlmostEqual(focus_at_frame(kf, 50), 2000, delta=0.1)

    def test_three_keyframes_pick_segment(self):
        kf = [(0, 3000), (100, 1000), (200, 500)]
        # segment 1: (1/3 + 1) / 2 D = 2/3 D = 1500 mm
        self.assertAlmostEqual(focus_at_frame(kf, 50), 1500, delta=0.1)
        # segment 2: (1 + 2) / 2 D = 1.5 D = 666.667 mm
        self.assertAlmostEqual(focus_at_frame(kf, 150), 2000 / 3, delta=0.1)
        self.assertEqual(focus_at_frame(kf, 100), 1000)

    def test_errors(self):
        with self.assertRaisesRegex(ValueError, "repeated"):
            focus_at_frame([(0, 1000), (0, 500)], 0)
        with self.assertRaises(ValueError):
            focus_at_frame([(10, 1000), (0, 500)], 0)
        with self.assertRaises(ValueError):
            focus_at_frame([(0, 1000)], 0)


if __name__ == "__main__":
    unittest.main()
