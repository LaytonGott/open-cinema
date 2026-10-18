import copy
import math
import statistics
import unittest

import open_optics.temporal
from open_optics.temporal import smooth_depth_sequence
from tests.temporal_synth import make_flicker_sequence


def _frames():
    return [
        [[0.0, 1.5, 2.0], [3.25, 0.0, 4.0], [5.0, 6.5, 0.5]],
        [[1.0, 0.0, 2.5], [3.0, 3.5, 4.5], [0.0, 6.0, 7.0]],
        [[2.0, 2.5, 0.0], [0.5, 1.0, 1.5], [8.0, 0.0, 9.5]],
        [[0.0, 0.25, 0.75], [1.25, 2.75, 0.0], [3.5, 4.25, 5.75]],
    ]


class TestInputUntouched(unittest.TestCase):
    def test_input_equals_deepcopy(self):
        frames = _frames()
        original = copy.deepcopy(frames)
        smooth_depth_sequence(frames, 0.7)
        self.assertEqual(frames, original)

    def test_output_independent(self):
        frames = _frames()
        original = copy.deepcopy(frames)
        output = smooth_depth_sequence(frames, 0.7)
        output[0][0][0] = 99.0
        output[1][0].append(1.0)
        self.assertEqual(frames, original)
        for out_frame, in_frame in zip(output, frames):
            self.assertIsNot(out_frame, in_frame)
            for out_row, in_row in zip(out_frame, in_frame):
                self.assertIsNot(out_row, in_row)


class TestTrivialSequences(unittest.TestCase):
    def test_empty(self):
        result = smooth_depth_sequence([])
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_single_frame_same_values(self):
        frame = [[2.0, 6.0], [3.5, 4.0]]
        frames = [frame]
        result = smooth_depth_sequence(frames, 0.7)
        self.assertEqual(result, [frame])
        self.assertIsNot(result, frames)
        self.assertIsNot(result[0], frame)
        for out_row, in_row in zip(result[0], frame):
            self.assertIsNot(out_row, in_row)

    def test_single_frame_strength_one(self):
        frame = [[2.0, 6.0], [3.5, 4.0]]
        frames = [frame]
        result = smooth_depth_sequence(frames, 1.0)
        self.assertEqual(result, [frame])
        self.assertIsNot(result, frames)
        self.assertIsNot(result[0], frame)
        for out_row, in_row in zip(result[0], frame):
            self.assertIsNot(out_row, in_row)


class TestSmoothShape(unittest.TestCase):
    def _frames(self):
        return [[[2, 2.0], [6.0, 6.0]] for _ in range(3)]

    def _check(self, result):
        self.assertEqual(len(result), 3)
        for frame in result:
            self.assertEqual(len(frame), 2)
            for row in frame:
                self.assertEqual(len(row), 2)
                for v in row:
                    self.assertIsInstance(v, float)

    def test_three_frames_2x2(self):
        self._check(smooth_depth_sequence(self._frames(), 0.5))

    def test_default_strength(self):
        self._check(smooth_depth_sequence(self._frames()))


class TestStrengthValidation(unittest.TestCase):
    def test_invalid_strengths_raise(self):
        for s in (-0.1, 1.5, float("nan"), float("inf"), True, "a"):
            with self.subTest(strength=s):
                with self.assertRaises((ValueError, TypeError)) as ctx:
                    smooth_depth_sequence([[[2.0]]], s)
                self.assertIn("strength", str(ctx.exception))

    def test_invalid_strength_raises_for_empty_frames(self):
        with self.assertRaises((ValueError, TypeError)) as ctx:
            smooth_depth_sequence([], 1.5)
        self.assertIn("strength", str(ctx.exception))

    def test_valid_strengths_accepted(self):
        for s in (0, 1, 0.0, 1.0, 0.5):
            with self.subTest(strength=s):
                self.assertIsInstance(smooth_depth_sequence([[[2.0]]], s), list)


class TestMalformedSequences(unittest.TestCase):
    def _raises(self, frames, text):
        with self.assertRaises(ValueError) as ctx:
            smooth_depth_sequence(frames)
        self.assertIn(text, str(ctx.exception))

    def test_different_heights(self):
        self._raises([[[1.0], [2.0]], [[1.0]]], "frame 1 has size 1x1")

    def test_different_widths(self):
        self._raises([[[1.0, 2.0]], [[1.0]]], "frame 1 has size 1x1")

    def test_ragged_row(self):
        self._raises([[[1.0, 2.0], [3.0]]], "frame 0 row 1 has length 1")

    def test_non_list_frame(self):
        self._raises([(([1.0],))], "frame 0 must be a list")
        self._raises([3], "frame 0 must be a list")

    def test_non_list_row(self):
        self._raises([[(1.0, 2.0)]], "frame 0 row 0 must be a list")

    def test_string_entry(self):
        self._raises([[["x"]]], "frame 0 row 0 entry 0")

    def test_bool_entry(self):
        self._raises([[[True]]], "frame 0 row 0 entry 0")

    def test_non_list_frames(self):
        self._raises(((([1.0],),),), "frames must be a list")

    def test_zero_rows_accepted(self):
        self.assertEqual(smooth_depth_sequence([[], []]), [[], []])

    def test_zero_columns_accepted(self):
        self.assertEqual(smooth_depth_sequence([[[]], [[]]]), [[[]], [[]]])


class TestStrengthZero(unittest.TestCase):
    def test_flicker_sequence_passthrough(self):
        noisy, _ = make_flicker_sequence(seed=5)
        original = copy.deepcopy(noisy)
        out = smooth_depth_sequence(noisy, 0)
        self.assertEqual(out, noisy)
        self.assertIsNot(out, noisy)
        self.assertEqual(noisy, original)

    def test_special_values_passthrough(self):
        frames = [[[float("nan"), float("inf")], [0.0, -1.0]],
                  [[1.0, 2.0], [float("nan"), 3.0]]]
        out = smooth_depth_sequence(frames, 0)
        self.assertTrue(math.isnan(out[0][0][0]))
        self.assertTrue(math.isnan(out[1][1][0]))
        self.assertEqual(out[0][0][1], float("inf"))
        self.assertEqual(out[0][1], [0.0, -1.0])
        self.assertEqual(out[1][0], [1.0, 2.0])
        self.assertEqual(out[1][1][1], 3.0)


class TestInvalidValues(unittest.TestCase):
    def _frames(self):
        nan, inf = float("nan"), float("inf")
        return [
            [[2.0, 2.0], [2.0, 2.0]],
            [[nan, 0.0], [inf, -inf]],
            [[-1.0, -1.0], [nan, 3.0]],
            [[inf, 0.0], [-inf, nan]],
            [[nan, -1.0], [0.0, inf]],
        ]

    def test_outputs_finite_positive_and_input_untouched(self):
        frames = self._frames()
        original = copy.deepcopy(frames)
        out = smooth_depth_sequence(frames, 0.7)
        self.assertEqual(len(out), 5)
        for frame in out:
            for row in frame:
                for v in row:
                    self.assertTrue(math.isfinite(v))
                    self.assertGreater(v, 0)
        for fa, fb in zip(frames, original):
            for ra, rb in zip(fa, fb):
                for a, b in zip(ra, rb):
                    self.assertTrue(a == b or (math.isnan(a) and math.isnan(b)))

    def test_nan_after_valid_holds_estimate(self):
        out = smooth_depth_sequence(self._frames(), 0.7)
        self.assertEqual(out[0][0][0], 2.0)
        self.assertEqual(out[1][0][0], 2.0)

    def test_zero_then_negative_stays_put(self):
        out = smooth_depth_sequence(self._frames(), 0.7)
        for i in range(5):
            self.assertEqual(out[i][0][1], 2.0)


class TestMissingAtStart(unittest.TestCase):
    def test_leading_missing_backfilled(self):
        vals = [float("nan"), 0.0, 3.0, 3.0, 3.0, 3.0]
        out = smooth_depth_sequence([[[v]] for v in vals], 0.7)
        self.assertEqual(len(out), 6)
        for frame in out:
            self.assertAlmostEqual(frame[0][0], 3.0, places=6)

    def test_never_valid_pixel(self):
        bad = [float("nan"), float("inf"), 0.0, -1.0]
        frames = [[[v, 2.0]] for v in bad]
        out = smooth_depth_sequence(frames, 0.7)
        self.assertEqual(len(out), 4)
        for frame in out:
            self.assertTrue(math.isfinite(frame[0][0]))
            self.assertGreater(frame[0][0], 0)
            self.assertAlmostEqual(frame[0][0], 1.0, places=6)
            self.assertAlmostEqual(frame[0][1], 2.0, places=6)


class TestSpikeRejection(unittest.TestCase):
    def _check(self, spike):
        frames = [[[2.0]] for _ in range(12)]
        frames[5] = [[spike]]
        out = smooth_depth_sequence(frames, 0.7)
        for frame in out:
            self.assertAlmostEqual(frame[0][0], 2.0, delta=0.06)

    def test_high_spike(self):
        self._check(6.0)

    def test_low_spike(self):
        self._check(0.5)


class TestPersistentChange(unittest.TestCase):
    def _step(self, strength):
        frames = [[[2.0]] if i < 10 else [[4.0]] for i in range(20)]
        out = smooth_depth_sequence(frames, strength)
        for i in range(10):
            self.assertAlmostEqual(out[i][0][0], 2.0, delta=0.04)
        self.assertAlmostEqual(out[15][0][0], 4.0, delta=0.6)

    def test_step_strength_07(self):
        self._step(0.7)

    def test_step_strength_09(self):
        self._step(0.9)

    def test_cut_followed(self):
        frames = [[[2.0]] if i < 5 else [[6.0]] for i in range(10)]
        out = smooth_depth_sequence(frames, 0.7)
        self.assertAlmostEqual(out[5][0][0], 2.0, delta=0.04)
        self.assertAlmostEqual(out[6][0][0], 6.0, delta=0.9)


def mean_abs_diff(frames):
    total = 0.0
    count = 0
    for t in range(1, len(frames)):
        for row, prev_row in zip(frames[t], frames[t - 1]):
            for a, b in zip(row, prev_row):
                total += abs(a - b)
                count += 1
    return total / count


class TestNoiseReduction(unittest.TestCase):
    def test_flicker_reduced(self):
        noisy, truth = make_flicker_sequence(seed=1, frames=40)
        out = smooth_depth_sequence(noisy, strength=0.7)
        self.assertLessEqual(mean_abs_diff(out), 0.4 * mean_abs_diff(noisy))

    def test_higher_strength_smoother(self):
        noisy, truth = make_flicker_sequence(seed=1, frames=40)
        low = smooth_depth_sequence(noisy, strength=0.3)
        high = smooth_depth_sequence(noisy, strength=0.9)
        self.assertLessEqual(mean_abs_diff(high), mean_abs_diff(low))


class TestAccuracy(unittest.TestCase):
    def test_mean_relative_error(self):
        for seed in (1, 2, 3):
            with self.subTest(seed=seed):
                noisy, truth = make_flicker_sequence(seed=seed, frames=40)
                out = smooth_depth_sequence(noisy, strength=0.7)
                total = 0.0
                count = 0
                for out_frame, true_frame in zip(out, truth):
                    for out_row, true_row in zip(out_frame, true_frame):
                        for a, b in zip(out_row, true_row):
                            total += abs(a - b) / b
                            count += 1
                self.assertLessEqual(total / count, 0.06)


class TestGlobalGain(unittest.TestCase):
    def test_gain_flicker_reduced(self):
        truth = [[2.0, 2.0, 6.0, 6.0] for _ in range(4)]
        frames = []
        for t in range(48):
            gain = 1 + 0.1 * math.sin(2 * math.pi * t / 8)
            frames.append([[v * gain for v in row] for row in truth])
        out = smooth_depth_sequence(frames, 0.7)
        for r, c in ((0, 0), (0, 3)):
            with self.subTest(true_depth=truth[r][c]):
                rel_in = [frames[t][r][c] / truth[r][c] for t in range(8, 48)]
                rel_out = [out[t][r][c] / truth[r][c] for t in range(8, 48)]
                self.assertLessEqual(statistics.pstdev(rel_out),
                                     0.7 * statistics.pstdev(rel_in))
        for out_frame in out:
            for out_row, true_row in zip(out_frame, truth):
                for a, b in zip(out_row, true_row):
                    self.assertLessEqual(abs(a - b) / b, 0.12)


class TestDeterminism(unittest.TestCase):
    def test_repeated_calls_equal(self):
        for strength in (0.7, 0.3):
            with self.subTest(strength=strength):
                noisy, _ = make_flicker_sequence(seed=7, frames=30)
                first = smooth_depth_sequence(noisy, strength)
                second = smooth_depth_sequence(noisy, strength)
                third = smooth_depth_sequence(copy.deepcopy(noisy), strength)
                self.assertEqual(first, second)
                self.assertEqual(first, third)


class TestMovingObject(unittest.TestCase):
    def test_near_object_is_tracked(self):
        width, count = 24, 30

        def covered(col, t):
            return t - 4 <= col < t

        frames = [
            [[1.0 if covered(c, t) else 5.0 for c in range(width)]]
            for t in range(count)
        ]
        out = smooth_depth_sequence(frames, 0.7)
        entered = 0
        left = 0
        for c in range(width):
            for t in range(1, count):
                if (covered(c, t) and not covered(c, t - 1)
                        and t + 2 < count and covered(c, t + 2)):
                    entered += 1
                    self.assertAlmostEqual(out[t + 2][0][c], 1.0, delta=0.15)
                if (covered(c, t - 1) and not covered(c, t) and t + 4 < count
                        and all(not covered(c, k) for k in range(t, t + 5))):
                    left += 1
                    self.assertAlmostEqual(out[t + 4][0][c], 5.0, delta=0.75)
        self.assertGreater(entered, 0)
        self.assertGreater(left, 0)


class TestDocs(unittest.TestCase):
    def test_docs_mention_key_terms(self):
        module_doc = open_optics.temporal.__doc__
        func_doc = smooth_depth_sequence.__doc__
        for word in ("metres", "spike", "missing"):
            self.assertIn(word, module_doc)
            self.assertIn(word, func_doc)
        self.assertIn("DepthOfField", module_doc)


if __name__ == "__main__":
    unittest.main()
