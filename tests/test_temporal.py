import copy
import unittest

from open_optics.temporal import smooth_depth_sequence


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


if __name__ == "__main__":
    unittest.main()
