import unittest

from open_optics.distortion import (
    DistortionError,
    distort_point,
    distort_point_opencv,
    opencv_to_library_coeffs,
    undistort_point,
    undistort_point_opencv,
)


class TestOpenCVCoeffs(unittest.TestCase):
    def test_reorders_five_coefficients(self):
        self.assertEqual(
            opencv_to_library_coeffs(-0.2, 0.05, 0.005, -0.003, 0.01),
            (-0.2, 0.05, 0.01, 0.005, -0.003),
        )

    def test_k3_defaults_to_zero(self):
        self.assertEqual(
            opencv_to_library_coeffs(-0.2, 0.05, 0.005, -0.003),
            (-0.2, 0.05, 0.0, 0.005, -0.003),
        )

    def test_nan_raises_value_error(self):
        with self.assertRaises(ValueError):
            opencv_to_library_coeffs(float("nan"), 0.05, 0.005, -0.003)


class TestDistortPointOpenCV(unittest.TestCase):
    COEFFS = (-0.2, 0.05, 0.005, -0.003, 0.01)

    def check(self, point, expected, coeffs):
        x, y = distort_point_opencv(*point, *coeffs)
        self.assertAlmostEqual(x, expected[0], places=9)
        self.assertAlmostEqual(y, expected[1], places=9)

    def test_small_point(self):
        self.check((0.05, 0.03),
                   (0.049955828919652, 0.029996617351791204), self.COEFFS)

    def test_larger_point(self):
        self.check((0.2, -0.15),
                   (0.19681205078125005, -0.14743716308593752), self.COEFFS)

    def test_edge_point(self):
        self.check((0.45, 0.3),
                   (0.4249701290390625, 0.285360919359375), self.COEFFS)

    def test_k1_only(self):
        self.check((0.05, 0.03), (0.049966, 0.0299796),
                   (-0.2, 0.0, 0.0, 0.0))

    def test_k3_default_zero(self):
        a = distort_point_opencv(0.2, -0.15, -0.2, 0.05, 0.005, -0.003)
        b = distort_point_opencv(0.2, -0.15, -0.2, 0.05, 0.005, -0.003, 0.0)
        self.assertEqual(a, b)

    def test_nan_raises_value_error(self):
        with self.assertRaises(ValueError):
            distort_point_opencv(float("nan"), 0.0, 0.0, 0.0, 0.0, 0.0)


class TestUndistortPointOpenCV(unittest.TestCase):
    COEFFS = (-0.2, 0.05, 0.005, -0.003, 0.01)

    def test_small_point(self):
        x, y = undistort_point_opencv(
            0.049955828919652, 0.029996617351791204, *self.COEFFS)
        self.assertAlmostEqual(x, 0.05, delta=1e-7)
        self.assertAlmostEqual(y, 0.03, delta=1e-7)

    def test_larger_point(self):
        x, y = undistort_point_opencv(
            0.19681205078125005, -0.14743716308593752, *self.COEFFS)
        self.assertAlmostEqual(x, 0.2, delta=1e-7)
        self.assertAlmostEqual(y, -0.15, delta=1e-7)

    def test_failure_raises(self):
        with self.assertRaisesRegex(DistortionError, "could not undistort"):
            undistort_point_opencv(0.5, 0.5, -50.0, 0.0, 0.0, 0.0)

    def test_non_finite_raises(self):
        with self.assertRaises(ValueError):
            undistort_point_opencv(float("nan"), 0.0, 0.0, 0.0, 0.0, 0.0)


class TestOrderEquivalence(unittest.TestCase):
    K1, K2, K3, P1, P2 = -0.2, 0.05, 0.01, 0.005, -0.003
    POINTS = [(0.05, 0.03), (0.2, -0.15), (0.45, 0.3), (-0.6, 0.5), (0.0, 0.0)]

    def test_distort_matches_library_order(self):
        for x, y in self.POINTS:
            self.assertEqual(
                distort_point_opencv(x, y, self.K1, self.K2, self.P1, self.P2, self.K3),
                distort_point(x, y, self.K1, self.K2, self.K3, self.P1, self.P2))

    def test_undistort_matches_library_order(self):
        for x, y in self.POINTS:
            self.assertEqual(
                undistort_point_opencv(x, y, self.K1, self.K2, self.P1, self.P2, self.K3),
                undistort_point(x, y, self.K1, self.K2, self.K3, self.P1, self.P2))

    def test_converter_matches_opencv(self):
        lib = opencv_to_library_coeffs(self.K1, self.K2, self.P1, self.P2, self.K3)
        for x, y in self.POINTS:
            self.assertEqual(
                distort_point(x, y, *lib),
                distort_point_opencv(x, y, self.K1, self.K2, self.P1, self.P2, self.K3))

    def test_unconverted_opencv_vector_differs(self):
        x, y = 0.45, 0.3
        cv = (self.K1, self.K2, self.P1, self.P2, self.K3)
        self.assertNotEqual(distort_point(x, y, *cv), distort_point_opencv(x, y, *cv))


class TestLibraryOrderUnchanged(unittest.TestCase):
    K1, K2, K3, P1, P2 = -0.2, 0.05, 0.01, 0.005, -0.003
    CASES = [
        ((0.05, 0.03), (0.049955828919652, 0.029996617351791204)),
        ((0.2, -0.15), (0.19681205078125005, -0.14743716308593752)),
        ((0.45, 0.3), (0.4249701290390625, 0.285360919359375)),
    ]

    def test_distort_matches_opencv_values(self):
        for point, expected in self.CASES:
            x, y = distort_point(
                *point, self.K1, self.K2, self.K3, self.P1, self.P2)
            self.assertAlmostEqual(x, expected[0], places=9)
            self.assertAlmostEqual(y, expected[1], places=9)

    def test_undistort_round_trip(self):
        for point, expected in self.CASES[:2]:
            x, y = undistort_point(
                *expected, self.K1, self.K2, self.K3, self.P1, self.P2)
            self.assertAlmostEqual(x, point[0], delta=1e-7)
            self.assertAlmostEqual(y, point[1], delta=1e-7)

    def test_positional_equals_keyword(self):
        self.assertEqual(
            distort_point(0.45, 0.3, -0.2, 0.05, 0.01, 0.005, -0.003),
            distort_point(0.45, 0.3, -0.2, 0.05, k3=0.01, p1=0.005, p2=-0.003))


if __name__ == "__main__":
    unittest.main()
