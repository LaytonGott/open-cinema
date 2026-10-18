import unittest

from open_optics.distortion import (
    DistortionError,
    distort_point,
    undistort_point,
)


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


class TestUndistortPoint(unittest.TestCase):
    def test_round_trip(self):
        points = [(1.0, 0.0), (0.6, 0.8), (0.3, -0.4), (0.0, 0.0)]
        for i in range(-6, 7):
            k1 = i * 0.05
            for x, y in points:
                x_u, y_u = undistort_point(*distort_point(x, y, k1=k1), k1=k1)
                self.assertAlmostEqual(x_u, x, delta=1e-6)
                self.assertAlmostEqual(y_u, y, delta=1e-6)

    def test_zero_coefficients(self):
        x, y = undistort_point(0.5, 0.3)
        self.assertAlmostEqual(x, 0.5, delta=1e-12)
        self.assertAlmostEqual(y, 0.3, delta=1e-12)

    def test_round_trip_all_coefficients(self):
        coeffs = dict(k1=-0.1, k2=0.01, p1=0.001, p2=0.001)
        x_u, y_u = undistort_point(*distort_point(0.5, 0.3, **coeffs), **coeffs)
        self.assertAlmostEqual(x_u, 0.5, delta=1e-6)
        self.assertAlmostEqual(y_u, 0.3, delta=1e-6)

    def test_failure_raises(self):
        with self.assertRaisesRegex(DistortionError, "could not undistort"):
            undistort_point(0.5, 0.5, k1=-50.0)


if __name__ == "__main__":
    unittest.main()
