import math
import unittest

from open_optics.summary import _fmt


class TestFmt(unittest.TestCase):
    def test_two_decimals(self):
        self.assertEqual(_fmt(39.6), "39.60")

    def test_rounds_third(self):
        self.assertEqual(_fmt(1 / 3), "0.33")

    def test_infinity(self):
        self.assertEqual(_fmt(math.inf), "inf")


if __name__ == "__main__":
    unittest.main()
