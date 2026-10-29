import math
import unittest

from open_optics.focus_pull import rack_focus_m


class RackFocusTest(unittest.TestCase):
    """Known values worked by hand: s = u^2 (3 - 2u), 1/d = (1 - s)/a + s/b."""

    def test_midpoint(self):
        # u = 0.5, s = 0.5: 1/d = 0.25 + 0.0625 = 0.3125, d = 3.2 m
        self.assertAlmostEqual(rack_focus_m(2, 8, 0.5), 3.2, places=9)

    def test_quarter_of_the_pull(self):
        # t = 0.35: u = 0.25, s = 0.15625: 1/d = 0.84375 * 0.5 + 0.15625 * 0.125 = 0.44140625
        self.assertAlmostEqual(rack_focus_m(2, 8, 0.35), 1 / 0.44140625, places=9)

    def test_holds_before_start_and_after_end(self):
        for t in (0.0, 0.1, 0.2):
            self.assertAlmostEqual(rack_focus_m(2, 8, t), 2.0, places=12)
        for t in (0.8, 0.9, 1.0):
            self.assertAlmostEqual(rack_focus_m(2, 8, t), 8.0, places=12)

    def test_custom_window(self):
        # start 0, end 1, t = 0.5: s = 0.5, 1/d = 0.1 + 0.5 = 0.6
        self.assertAlmostEqual(rack_focus_m(5, 1, 0.5, 0.0, 1.0), 1 / 0.6, places=9)

    def test_bad_values(self):
        for args in ((0, 8, 0.5), (2, -1, 0.5), (2, math.inf, 0.5), (math.nan, 8, 0.5), (2, 8, 1.5), (2, 8, -0.1),
                     (2, 8, 0.5, 0.6, 0.6), (2, 8, 0.5, 0.7, 0.3), (2, 8, 0.5, -0.1, 0.5), (2, 8, 0.5, 0.2, 1.1)):
            with self.assertRaises(ValueError, msg=str(args)):
                rack_focus_m(*args)


if __name__ == "__main__":
    unittest.main()
