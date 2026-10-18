import unittest

from open_optics.distortion import (
    DistortionError,
    border_free_zoom,
    classify_distortion,
    distort_pixel,
    distort_point,
    straight_line_deviation,
    undistort_pixel,
    undistort_point,
)
from open_optics.lens import Lens
from open_optics.sensor import Sensor


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


class TestPixelDistortion(unittest.TestCase):
    W, H = 1920, 1080
    CX, CY = 959.5, 539.5

    def setUp(self):
        self.sensor = Sensor(36, 24)
        self.lens = Lens(50, 2.8, 22)

    def args(self):
        return (self.sensor, self.lens, self.W, self.H)

    def test_zero_coefficients_unchanged(self):
        for p in [(0, 0), (100.5, 700.25), (1919, 1079)]:
            for fn in (distort_pixel, undistort_pixel):
                x, y = fn(*p, *self.args())
                self.assertAlmostEqual(x, p[0], places=9)
                self.assertAlmostEqual(y, p[1], places=9)

    def test_zero_coefficients_zoom_is_one(self):
        self.assertEqual(border_free_zoom(*self.args()), 1.0)

    def test_centre_fixed(self):
        x, y = distort_pixel(self.CX, self.CY, *self.args(), k1=-0.2)
        self.assertAlmostEqual(x, self.CX, places=9)
        self.assertAlmostEqual(y, self.CY, places=9)

    def test_round_trip(self):
        for p in [(0, 0), (300.5, 800.0), (1500.0, 100.0), (1919, 1079)]:
            q = distort_pixel(*p, *self.args(), k1=-0.1)
            x, y = undistort_pixel(*q, *self.args(), k1=-0.1)
            self.assertAlmostEqual(x, p[0], delta=1e-4)
            self.assertAlmostEqual(y, p[1], delta=1e-4)

    def test_barrel_zoom_at_least_one(self):
        self.assertGreaterEqual(border_free_zoom(*self.args(), k1=-0.2), 1.0)

    def test_border_pixels_inside_source(self):
        eps = 1e-6
        n = 16
        for i in range(-3, 4):
            k1 = i / 10
            z = border_free_zoom(*self.args(), k1=k1)
            for j in range(n + 1):
                t = j / n
                border = [(t * (self.W - 1), 0), (t * (self.W - 1), self.H - 1),
                          (0, t * (self.H - 1)), (self.W - 1, t * (self.H - 1))]
                for px, py in border:
                    u = self.CX + (px - self.CX) / z
                    v = self.CY + (py - self.CY) / z
                    x, y = distort_pixel(u, v, *self.args(), k1=k1)
                    self.assertTrue(-eps <= x <= self.W - 1 + eps, (k1, px, py, x))
                    self.assertTrue(-eps <= y <= self.H - 1 + eps, (k1, px, py, y))

    def test_pincushion_zoom_above_one(self):
        self.assertGreater(border_free_zoom(*self.args(), k1=0.2), 1.0)


class TestClassifyDistortion(unittest.TestCase):
    def test_barrel(self):
        # 1 - 0.1 * 0.5**2 = 0.975 < 1
        self.assertEqual(classify_distortion(k1=-0.1), "barrel")

    def test_pincushion(self):
        self.assertEqual(classify_distortion(k1=0.1), "pincushion")

    def test_neutral(self):
        self.assertEqual(classify_distortion(), "neutral")


class TestStraightLineDeviation(unittest.TestCase):
    def setUp(self):
        self.points = [(0.5, -0.5 + i * 0.05) for i in range(21)]

    def test_straight_line_is_zero(self):
        self.assertLess(straight_line_deviation(self.points), 1e-12)

    def test_barrel_bows_line(self):
        # middle x = 0.5 * (1 - 0.1 * 0.25) = 0.4875, ends x = 0.475
        distorted = [distort_point(x, y, k1=-0.1) for x, y in self.points]
        self.assertGreater(straight_line_deviation(distorted), 0.001)

    def test_undistort_straightens_line(self):
        distorted = [distort_point(x, y, k1=-0.1) for x, y in self.points]
        restored = [undistort_point(x, y, k1=-0.1) for x, y in distorted]
        self.assertLess(straight_line_deviation(restored), 0.001)

    def test_single_point_raises(self):
        with self.assertRaises(ValueError):
            straight_line_deviation([(0.0, 0.0)])


class TestDistortionDocstrings(unittest.TestCase):
    def test_no_lens_relative_wording(self):
        self.assertNotIn("lens-relative", border_free_zoom.__doc__)
        self.assertNotIn("lens-relative", classify_distortion.__doc__)


if __name__ == "__main__":
    unittest.main()
