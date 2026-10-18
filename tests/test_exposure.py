import unittest

from open_optics.exposure import (
    f_from_t_stop,
    f_number_to_stops,
    stop_difference,
    stops_to_f_number,
    t_stop_from_f,
)


class TestStops(unittest.TestCase):
    def test_stop_difference_hand_worked(self):
        # 2 * log2(4 / 2.8) = 1.03
        self.assertAlmostEqual(stop_difference(2.8, 4.0), 1.0, delta=0.05)

    def test_stop_difference_equal_apertures(self):
        self.assertAlmostEqual(stop_difference(2.8, 2.8), 0.0, places=9)

    def test_f_number_to_stops(self):
        self.assertAlmostEqual(f_number_to_stops(1.0), 0.0, places=9)
        self.assertAlmostEqual(f_number_to_stops(2.0), 2.0, places=9)

    def test_stops_to_f_number(self):
        self.assertAlmostEqual(stops_to_f_number(2), 2.0, places=9)

    def test_f_number_errors(self):
        for bad in (0, -2.0):
            with self.assertRaises(ValueError):
                f_number_to_stops(bad)


class TestTStop(unittest.TestCase):
    def test_t_stop_from_f(self):
        # 2 * 2 ** 0.15 = 2.2191
        self.assertAlmostEqual(t_stop_from_f(2.0, 0.3), 2.2191, delta=0.001)

    def test_zero_loss_unchanged(self):
        self.assertAlmostEqual(t_stop_from_f(2.8, 0), 2.8, places=9)
        self.assertAlmostEqual(f_from_t_stop(2.8, 0), 2.8, places=9)

    def test_round_trip(self):
        t = t_stop_from_f(2.8, 0.5)
        self.assertAlmostEqual(f_from_t_stop(t, 0.5), 2.8, places=9)

    def test_negative_loss_raises(self):
        with self.assertRaises(ValueError):
            t_stop_from_f(2.0, -0.1)
        with self.assertRaises(ValueError):
            f_from_t_stop(2.0, -0.1)

    def test_nonpositive_f_number_raises(self):
        for bad in (0, -2.0):
            with self.assertRaises(ValueError):
                t_stop_from_f(bad, 0.3)


if __name__ == "__main__":
    unittest.main()
