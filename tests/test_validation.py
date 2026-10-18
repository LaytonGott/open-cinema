import math
import unittest

from open_optics.validation import (
    require_finite,
    require_positive,
    require_positive_or_inf,
)


class TestRequirePositive(unittest.TestCase):
    def test_valid_returns_float(self):
        result = require_positive("focal_length_mm", 50)
        self.assertEqual(result, 50.0)
        self.assertIsInstance(result, float)

    def test_zero_and_negative_rejected_with_name(self):
        for bad in (0, -5):
            with self.assertRaises(ValueError) as ctx:
                require_positive("focal_length_mm", bad)
            self.assertIn("focal_length_mm", str(ctx.exception))

    def test_string_raises_type_error(self):
        with self.assertRaises(TypeError) as ctx:
            require_positive("focal_length_mm", "50")
        self.assertIn(
            "focal_length_mm must be a number, got '50' (str)", str(ctx.exception)
        )

    def test_none_and_bool_raise_type_error(self):
        for bad in (None, True):
            with self.assertRaises(TypeError):
                require_positive("x", bad)

    def test_nan_and_inf_rejected(self):
        for bad in (math.nan, math.inf):
            with self.assertRaises(ValueError):
                require_positive("x", bad)


class TestRequirePositiveOrInf(unittest.TestCase):
    def test_inf_accepted(self):
        self.assertEqual(require_positive_or_inf("x", math.inf), math.inf)

    def test_valid_returns_float(self):
        self.assertEqual(require_positive_or_inf("x", 50), 50.0)

    def test_rejected_values(self):
        for bad in (0, -5, math.nan, -math.inf):
            with self.assertRaises(ValueError):
                require_positive_or_inf("x", bad)

    def test_string_raises_type_error(self):
        with self.assertRaises(TypeError):
            require_positive_or_inf("x", "50")


class TestRequireFinite(unittest.TestCase):
    def test_valid_values(self):
        self.assertEqual(require_finite("x", -5), -5.0)
        self.assertEqual(require_finite("x", 0), 0.0)

    def test_nan_and_inf_rejected(self):
        for bad in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                require_finite("x", bad)

    def test_string_raises_type_error(self):
        with self.assertRaises(TypeError):
            require_finite("x", "50")


if __name__ == "__main__":
    unittest.main()
