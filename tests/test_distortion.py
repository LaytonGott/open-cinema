import unittest

from open_optics.distortion import distort_point


class TestDistortPoint(unittest.TestCase):
    def test_radial_known_value(self):
        # r2 = 0.34, radial = 1 - 0.034 + 0.01 * 0.1156 = 0.967156
        x_d, y_d = distort_point(0.5, 0.3, k1=-0.1, k2=0.01)
        self.assertAlmostEqual(x_d, 0.483578, places=5)
        self.assertAlmostEqual(y_d, 0.2901468, places=5)

    def test_zero_coefficients_identity(self):
        for point in [(0.5, 0.3), (-1, 2), (0, 0)]:
            self.assertEqual(distort_point(*point), point)

    def test_origin_fixed(self):
        result = distort_point(0, 0, k1=0.1, k2=0.02, k3=0.01, p1=0.01, p2=0.01)
        self.assertEqual(result, (0, 0))

    def test_tangential_p1(self):
        # r2 = 0.25: x_d = 0.5, y_d = 0.01 * 0.25 = 0.0025
        x_d, y_d = distort_point(0.5, 0, p1=0.01)
        self.assertAlmostEqual(x_d, 0.5, places=9)
        self.assertAlmostEqual(y_d, 0.0025, places=9)

    def test_tangential_p2(self):
        # x_d = 0.5 + 0.01 * (0.25 + 0.5) = 0.5075
        x_d, y_d = distort_point(0.5, 0, p2=0.01)
        self.assertAlmostEqual(x_d, 0.5075, places=9)
        self.assertAlmostEqual(y_d, 0.0, places=9)

    def test_non_finite_raises(self):
        with self.assertRaises(ValueError):
            distort_point(float("nan"), 0.0)
        with self.assertRaises(ValueError):
            distort_point(0.0, float("inf"))


if __name__ == "__main__":
    unittest.main()
