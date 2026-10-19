import unittest

import torch

from open_optics.depth import subject_median
from open_optics_nodes.depth_to_metric import _median_tensor


def _f64(values):
    return torch.tensor(values, dtype=torch.float64)


class MedianTensorTests(unittest.TestCase):
    def test_odd_hand_value(self):
        self.assertAlmostEqual(_median_tensor(_f64([3, 1, 2])), 2.0, places=9)

    def test_even_hand_value(self):
        self.assertAlmostEqual(_median_tensor(_f64([4, 1, 3, 2])), 2.5, places=9)

    def test_matches_subject_median_random(self):
        gen = torch.Generator().manual_seed(1234)
        for n in (1001, 1000):
            values = torch.rand(n, generator=gen, dtype=torch.float64) + 0.01
            self.assertAlmostEqual(
                _median_tensor(values), subject_median(values.tolist()), delta=1e-12
            )

    def test_nan_raises(self):
        with self.assertRaises(ValueError):
            _median_tensor(_f64([1.0, float("nan"), 2.0]))

    def test_non_positive_median_raises(self):
        with self.assertRaises(ValueError):
            _median_tensor(_f64([-1.0, 0.0, -2.0]))

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            _median_tensor(_f64([]))


if __name__ == "__main__":
    unittest.main()
