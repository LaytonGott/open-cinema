import unittest

from open_optics.distortion import distort_point


class TestDistortPointEdgeCases(unittest.TestCase):
    def test_zero_coefficients_returns_input(self):
        x_d, y_d = distort_point(0.3, 0.4)
        self.assertAlmostEqual(x_d, 0.3, places=12)
        self.assertAlmostEqual(y_d, 0.4, places=12)

    def test_centre_unchanged_with_k1(self):
        x_d, y_d = distort_point(0, 0, k1=0.2)
        self.assertAlmostEqual(x_d, 0.0, places=12)
        self.assertAlmostEqual(y_d, 0.0, places=12)


if __name__ == "__main__":
    unittest.main()
