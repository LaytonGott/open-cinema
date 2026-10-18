"""Tests for the seeded synthetic flicker sequence builder."""

import unittest

from tests.temporal_synth import count_flicker, make_flicker_sequence


class TestTemporalSynth(unittest.TestCase):
    def test_same_seed_identical(self):
        a = make_flicker_sequence(seed=3)
        b = make_flicker_sequence(seed=3)
        self.assertEqual(a[0], b[0])
        self.assertEqual(a[1], b[1])

    def test_different_seed_differs(self):
        a_noisy, a_truth = make_flicker_sequence(seed=3)
        b_noisy, b_truth = make_flicker_sequence(seed=4)
        self.assertNotEqual(a_noisy, b_noisy)
        self.assertEqual(a_truth, b_truth)

    def test_shape(self):
        noisy, truth = make_flicker_sequence(seed=1)
        for seq in (noisy, truth):
            self.assertEqual(len(seq), 40)
            for frame in seq:
                self.assertEqual(len(frame), 8)
                for row in frame:
                    self.assertEqual(len(row), 8)

    def test_truth_two_planes(self):
        _, truth = make_flicker_sequence(seed=1)
        values = {v for frame in truth for row in frame for v in row}
        self.assertEqual(values, {2.0, 6.0})

    def test_contains_flicker_types(self):
        frames, height, width = 60, 16, 16
        noisy, truth = make_flicker_sequence(
            seed=3, frames=frames, height=height, width=width)
        counts = count_flicker(noisy, truth)
        total = frames * height * width
        self.assertGreater(counts['dropouts'], 0)
        self.assertGreater(counts['spikes'], 0)
        self.assertTrue(0.015 <= counts['dropouts'] / total <= 0.045)
        self.assertTrue(0.008 <= counts['spikes'] / total <= 0.035)

        means = []
        for nf, tf in zip(noisy, truth):
            vals = []
            for r in range(height // 2):
                for n, t in zip(nf[r], tf[r]):
                    if n != 0.0 and n <= 2.5 * t:
                        vals.append(n)
            means.append(sum(vals) / len(vals))
        self.assertGreaterEqual(max(means) / min(means), 1.10)


if __name__ == '__main__':
    unittest.main()
