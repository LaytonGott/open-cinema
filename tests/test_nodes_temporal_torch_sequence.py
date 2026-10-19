import unittest

import torch

from open_optics.temporal import smooth_depth_sequence
from open_optics_nodes.temporal_torch import smooth_sequence_torch

NAN = float("nan")
CPU = torch.device("cpu")


def _make():
    d = torch.full((6, 4, 4), 2.0)
    d[:2, 0, 0] = NAN  # leading nan frames
    d[:, 1, 1] = NAN  # never valid
    d[3, 2, 2] = 20.0  # spike
    d[3:, 3, 3] = 8.0  # step change
    d[:, 0, 1] = torch.tensor([1.0, 1.2, 1.1, 1.3, 1.2, 1.4])
    return d


class SmoothSequenceTorchTest(unittest.TestCase):
    def test_matches_core(self):
        d = _make()
        want = smooth_depth_sequence(d.tolist(), 0.7)
        for chunk in (1, 3, 6):
            got, _ = smooth_sequence_torch(d, 0.7, chunk, CPU)
            self.assertEqual(got.dtype, torch.float32)
            for t in range(6):
                for r in range(4):
                    for c in range(4):
                        self.assertAlmostEqual(got[t, r, c].item(), want[t][r][c], delta=1e-4)

    def test_strength_zero(self):
        d = _make()
        got, _ = smooth_sequence_torch(d, 0, 3, CPU)
        self.assertTrue(torch.equal(torch.nan_to_num(got, nan=-1.0), torch.nan_to_num(d, nan=-1.0)))

    def test_used_device_cpu(self):
        _, dev = smooth_sequence_torch(_make(), 0.5, 2, CPU)
        self.assertEqual(dev.type, "cpu")

    def test_bad_strength(self):
        with self.assertRaises(ValueError):
            smooth_sequence_torch(_make(), 1.5, 2, CPU)


if __name__ == "__main__":
    unittest.main()
