import unittest

from open_optics.distortion import opencv_to_library_coeffs


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


if __name__ == "__main__":
    unittest.main()
