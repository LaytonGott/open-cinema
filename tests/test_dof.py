import math
import unittest

from open_optics.dof import dof_limits_mm, hyperfocal_mm


class TestDof(unittest.TestCase):
    def test_hyperfocal_known_value(self):
        # 50^2 / (2.8 * 0.029) + 50 = 30838.1 mm
        self.assertAlmostEqual(hyperfocal_mm(50, 2.8, 0.029), 30838.1, delta=1)

    def test_limits_known_values(self):
        near, far = dof_limits_mm(50, 2.8, 3000, 0.029)
        self.assertAlmostEqual(near, 2737.7, delta=0.5)
        self.assertAlmostEqual(far, 3317.9, delta=0.5)

    def test_beyond_hyperfocal_far_is_inf(self):
        near, far = dof_limits_mm(50, 2.8, 40000, 0.029)
        self.assertEqual(far, math.inf)
        self.assertTrue(math.isfinite(near))

    def test_at_hyperfocal_far_is_inf(self):
        h = hyperfocal_mm(50, 2.8, 0.029)
        near, far = dof_limits_mm(50, 2.8, h, 0.029)
        self.assertEqual(far, math.inf)
        self.assertTrue(math.isfinite(near))

    def test_infinite_focus_rejected(self):
        with self.assertRaises(ValueError):
            dof_limits_mm(50, 2.8, math.inf, 0.029)


if __name__ == "__main__":
    unittest.main()
