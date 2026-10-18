"""Tests for open_optics.depth with hand-worked values."""

import unittest

from open_optics.depth import (
    depth_to_metric,
    fit_depth_mapping,
    percentile,
    validate_depth_params,
)


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


if __name__ == "__main__":
    unittest.main()
