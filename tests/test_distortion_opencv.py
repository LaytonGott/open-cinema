import unittest

from open_optics.distortion import (
    DistortionError,
    opencv_to_library_coeffs,
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


if __name__ == "__main__":
    unittest.main()
