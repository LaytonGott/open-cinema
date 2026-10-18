import math
import unittest

from open_optics.chromatic import channel_scales, fringe_shift_px


class ChannelScalesTest(unittest.TestCase):
    def test_scales(self):
        r, b = channel_scales(0.001, -0.002)
        self.assertAlmostEqual(r, 1.001, places=9)
        self.assertAlmostEqual(b, 0.998, places=9)


class FringeShiftTest(unittest.TestCase):
    def test_centre_is_zero(self):
        red, blue = fringe_shift_px(959.5, 539.5, 1920, 1080, 0.001, -0.001)
        self.assertEqual(red, (0.0, 0.0))
        self.assertEqual(blue, (0.0, 0.0))

    def test_corner_red(self):
        red, _ = fringe_shift_px(0, 0, 1920, 1080, red=0.001, blue=-0.001)
        self.assertAlmostEqual(math.hypot(*red), 1.10067, places=3)
        self.assertAlmostEqual(red[0], -0.9595, places=3)
        self.assertAlmostEqual(red[1], -0.5395, places=3)

    def test_corner_blue_opposite_sign(self):
        _, blue = fringe_shift_px(0, 0, 1920, 1080, red=0.001, blue=-0.001)
        self.assertAlmostEqual(blue[0], 0.9595, places=3)
        self.assertAlmostEqual(blue[1], 0.5395, places=3)


if __name__ == "__main__":
    unittest.main()
