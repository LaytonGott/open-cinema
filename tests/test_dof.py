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

    def test_cross_check_independent_form(self):
        def reference(f, n, s, c):
            near = s * f * f / (f * f + n * c * (s - f))
            denominator_far = f * f - n * c * (s - f)
            far = s * f * f / denominator_far if denominator_far > 0 else math.inf
            return near, far

        # (focal_mm, f_number, focus_mm, coc_mm)
        cases = [
            (50, 2.8, 3000, 0.029),
            (24, 1.4, 1000, 0.03),
            (24, 4, 2000, 0.025),
            (24, 8, 10000, 0.03),
            (28, 2, 500, 0.02),
            (35, 1.4, 1500, 0.015),
            (35, 5.6, 3000, 0.03),
            (35, 16, 5000, 0.03),
            (50, 1.4, 800, 0.02),
            (50, 8, 5000, 0.025),
            (50, 16, 20000, 0.03),
            (50, 2.8, 100000, 0.029),
            (85, 1.8, 2500, 0.015),
            (85, 4, 10000, 0.03),
            (85, 11, 8000, 0.025),
            (100, 2.8, 4000, 0.02),
            (100, 16, 30000, 0.03),
            (135, 2, 6000, 0.015),
            (135, 8, 15000, 0.03),
            (135, 16, 50000, 0.03),
        ]
        self.assertEqual(len(cases), 20)
        inf_count = 0
        for f, n, s, c in cases:
            with self.subTest(f=f, n=n, s=s, c=c):
                near, far = dof_limits_mm(f, n, s, c)
                ref_near, ref_far = reference(f, n, s, c)
                self.assertLess(abs(near - ref_near) / ref_near, 1e-9)
                if math.isinf(ref_far):
                    inf_count += 1
                    self.assertEqual(far, math.inf)
                else:
                    self.assertLess(abs(far - ref_far) / ref_far, 1e-9)
                ref_h = f * f / (n * c) + f
                h = hyperfocal_mm(f, n, c)
                self.assertLess(abs(h - ref_h) / ref_h, 1e-9)
        self.assertGreaterEqual(inf_count, 3)


if __name__ == "__main__":
    unittest.main()
