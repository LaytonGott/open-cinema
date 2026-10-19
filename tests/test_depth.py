"""Tests for open_optics.depth with hand-worked values."""

import unittest

from open_optics.depth import (
    depth_to_metric,
    fit_depth_mapping,
    metric_depth_coefficients,
    percentile,
    subject_median,
    subject_pixel,
    subject_scale_metric,
    validate_depth_params,
    validate_subject_depth,
)


class TestValidateSubjectDepth(unittest.TestCase):
    def test_unusable_values_raise(self):
        for value, text in ((0.0, "0.0"), (-1.0, "-1.0"),
                            (float("nan"), "nan"), (float("inf"), "inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as ctx:
                    validate_subject_depth(value)
                self.assertIn("subject depth", str(ctx.exception))
                self.assertIn(text, str(ctx.exception))

    def test_positive_value_ok(self):
        self.assertIsNone(validate_subject_depth(0.5))


class TestInverseMapping(unittest.TestCase):
    def test_fit_parameters(self):
        # a = (1/1 - 1/5)/1 = 0.8, b = 1/1 - 0.8*1 = 0.2
        a, b = fit_depth_mapping(0, 1, 1, 5, True)
        self.assertAlmostEqual(a, 0.8, places=6)
        self.assertAlmostEqual(b, 0.2, places=6)

    def test_values_metres(self):
        self.assertAlmostEqual(depth_to_metric(1, 0, 1, 1, 5, True), 1.0, places=6)
        self.assertAlmostEqual(depth_to_metric(0, 0, 1, 1, 5, True), 5.0, places=6)
        # 1/(0.8*0.5+0.2) = 1/0.6
        self.assertAlmostEqual(
            depth_to_metric(0.5, 0, 1, 1, 5, True), 1 / 0.6, places=6
        )

    def test_clamps(self):
        self.assertAlmostEqual(depth_to_metric(2, 0, 1, 1, 5, True), 1.0, places=6)
        self.assertAlmostEqual(depth_to_metric(-2, 0, 1, 1, 5, True), 5.0, places=6)


class TestLinearMapping(unittest.TestCase):
    def test_values_metres(self):
        self.assertAlmostEqual(depth_to_metric(0, 0, 1, 1, 5, False), 1.0, places=6)
        self.assertAlmostEqual(depth_to_metric(1, 0, 1, 1, 5, False), 5.0, places=6)
        self.assertAlmostEqual(depth_to_metric(0.5, 0, 1, 1, 5, False), 3.0, places=6)

    def test_clamps(self):
        self.assertAlmostEqual(depth_to_metric(-3, 0, 1, 1, 5, False), 1.0, places=6)
        self.assertAlmostEqual(depth_to_metric(7, 0, 1, 1, 5, False), 5.0, places=6)


class TestDegenerate(unittest.TestCase):
    def test_equal_bounds_give_midpoint(self):
        for inverse in (True, False):
            self.assertAlmostEqual(
                depth_to_metric(0.3, 0.5, 0.5, 1, 5, inverse), 3.0, places=6
            )


class TestPercentile(unittest.TestCase):
    def test_median(self):
        self.assertAlmostEqual(percentile([0, 1, 2, 3, 4], 50), 2.0, places=6)

    def test_interpolated(self):
        self.assertAlmostEqual(percentile([0, 10], 25), 2.5, places=6)


class TestValidate(unittest.TestCase):
    def test_valid(self):
        self.assertIsNone(validate_depth_params(1, 5, 2, 98))

    def test_invalid(self):
        bad = [
            (0, 5, 2, 98),  # near 0
            (5, 5, 2, 98),  # far == near
            (1, 5, 98, 2),  # low > high
            (1, 5, 50, 50),  # low == high
            (1, 5, 2, 101),  # high > 100
            (1, 5, -1, 98),  # low < 0
        ]
        for args in bad:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    validate_depth_params(*args)


class TestMetricDepthCoefficients(unittest.TestCase):
    def assertCoefficients(self, got, want):
        self.assertAlmostEqual(got[0], want[0], places=9)
        self.assertAlmostEqual(got[1], want[1], places=9)
        self.assertIs(got[2], want[2])

    def test_inverse(self):
        self.assertCoefficients(metric_depth_coefficients(0, 1, 1, 5, True), (0.8, 0.2, True))

    def test_linear(self):
        self.assertCoefficients(metric_depth_coefficients(0, 1, 1, 5, False), (4.0, 1.0, False))

    def test_constant(self):
        self.assertCoefficients(metric_depth_coefficients(0.5, 0.5, 1, 5, True), (0.0, 3.0, False))


class TestSubjectPixel(unittest.TestCase):
    def test_centre(self):
        self.assertEqual(subject_pixel(0.5, 0.5, 9, 9), (4, 4))

    def test_origin(self):
        self.assertEqual(subject_pixel(0, 0, 9, 9), (0, 0))

    def test_far_corner(self):
        self.assertEqual(subject_pixel(1, 1, 9, 9), (8, 8))

    def test_non_square(self):
        self.assertEqual(subject_pixel(1, 1, 9, 5), (8, 4))


class TestSubjectMedian(unittest.TestCase):
    def test_even_count(self):
        self.assertAlmostEqual(subject_median([1, 2, 3, 10]), 2.5, places=9)

    def test_odd_count(self):
        self.assertAlmostEqual(subject_median([1, 2, 9]), 2.0, places=9)

    def test_outlier_does_not_move_it(self):
        self.assertAlmostEqual(subject_median([5, 5, 5, 5, 1000]), 5.0, places=9)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            subject_median([])

    def test_nan_raises(self):
        with self.assertRaises(ValueError):
            subject_median([1, float("nan")])


class TestSubjectScaleMetric(unittest.TestCase):
    def test_inverse(self):
        self.assertAlmostEqual(subject_scale_metric(0.4, 0.8, 2, True), 4.0, places=9)
        self.assertAlmostEqual(subject_scale_metric(1.6, 0.8, 2, True), 1.0, places=9)

    def test_depth_like(self):
        self.assertAlmostEqual(subject_scale_metric(0.4, 0.8, 2, False), 1.0, places=9)
        self.assertAlmostEqual(subject_scale_metric(1.6, 0.8, 2, False), 4.0, places=9)

    def test_at_subject(self):
        self.assertAlmostEqual(subject_scale_metric(0.8, 0.8, 2, True), 2.0, places=9)
        self.assertAlmostEqual(subject_scale_metric(0.8, 0.8, 2, False), 2.0, places=9)

    def test_inverse_non_positive_is_inf(self):
        self.assertEqual(subject_scale_metric(0, 0.8, 2, True), float("inf"))
        self.assertEqual(subject_scale_metric(-1, 0.8, 2, True), float("inf"))


if __name__ == "__main__":
    unittest.main()
