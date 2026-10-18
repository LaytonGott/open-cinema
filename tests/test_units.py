import math
import unittest

from open_optics.units import deg_to_rad, rad_to_deg


class TestUnits(unittest.TestCase):
    def test_180_degrees_is_pi(self):
        self.assertAlmostEqual(deg_to_rad(180), math.pi, places=12)

    def test_pi_is_180_degrees(self):
        self.assertAlmostEqual(rad_to_deg(math.pi), 180, places=12)

    def test_90_degrees_is_half_pi(self):
        self.assertAlmostEqual(deg_to_rad(90), math.pi / 2, places=12)

    def test_round_trip(self):
        self.assertAlmostEqual(rad_to_deg(deg_to_rad(37.5)), 37.5, places=12)


if __name__ == "__main__":
    unittest.main()
