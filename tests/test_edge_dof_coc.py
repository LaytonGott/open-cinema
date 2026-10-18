import math
import unittest

from open_optics.coc import blur_diameter_mm
from open_optics.dof import dof_limits_mm, hyperfocal_mm
from open_optics.fov import angle_of_view


class TestEdgeDofCoc(unittest.TestCase):
    def test_far_limit_infinite_beyond_hyperfocal(self):
        # hyperfocal = 50^2 / (2 * 0.03) + 50 = 41716.7 mm < 50000 mm
        _near, far = dof_limits_mm(50, 2, 50000, 0.03)
        self.assertEqual(far, math.inf)

    def test_blur_diameter_infinity_subject(self):
        # hand: 2500 / (2 * 1950) = 0.6410 mm
        self.assertAlmostEqual(blur_diameter_mm(50, 2, 2000, math.inf), 0.6410, delta=0.001)

    def test_angle_of_view_zero_focal_raises(self):
        with self.assertRaises(ValueError):
            angle_of_view(0, 36)

    def test_hyperfocal_negative_f_number_raises(self):
        with self.assertRaises(ValueError):
            hyperfocal_mm(50, -2, 0.03)


if __name__ == "__main__":
    unittest.main()
