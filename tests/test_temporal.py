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


if __name__ == "__main__":
    unittest.main()
