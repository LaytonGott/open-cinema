import math
import unittest

import torch

from open_optics.temporal import smooth_depth_sequence
from tests.temporal_synth import make_flicker_sequence
from open_optics_nodes.depth_temporal_smooth import OpenOptics_DepthTemporalSmooth


class TestDepthTemporalSmoothNode(unittest.TestCase):
    def test_output_shape_and_dtype(self):
        g = torch.Generator().manual_seed(0)
        depth = (torch.rand(5, 8, 8, generator=g) * 5.0 + 1.0).to(torch.float32)
        (out,) = OpenOptics_DepthTemporalSmooth().smooth(depth, 0.7)
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(tuple(out.shape), (5, 8, 8))

    def test_strength_input_spec(self):
        spec = OpenOptics_DepthTemporalSmooth.INPUT_TYPES()["required"]["strength"]
        self.assertEqual(spec[1]["default"], 0.7)
        self.assertEqual(spec[1]["min"], 0.0)
        self.assertEqual(spec[1]["max"], 1.0)

    def test_strength_zero_returns_input(self):
        g = torch.Generator().manual_seed(1)
        depth = (torch.rand(4, 6, 6, generator=g) * 5.0 + 1.0).to(torch.float32)
        (out,) = OpenOptics_DepthTemporalSmooth().smooth(depth, 0.0)
        for a, b in zip(out.flatten().tolist(), depth.flatten().tolist()):
            self.assertAlmostEqual(a, b, places=5)

    def test_matches_core_smoothing(self):
        seq, _truth = make_flicker_sequence(seed=3, frames=12, height=6, width=6)
        for strength in (0.7, 0.3):
            core = smooth_depth_sequence(seq, strength)
            (out,) = OpenOptics_DepthTemporalSmooth().smooth(
                torch.tensor(seq, dtype=torch.float32), strength)
            self.assertEqual(tuple(out.shape), (12, 6, 6))
            for t in range(12):
                for r in range(6):
                    for c in range(6):
                        expected = core[t][r][c]
                        got = out[t, r, c].item()
                        self.assertAlmostEqual(got, expected, delta=1e-5)
                        if expected > 0:
                            self.assertTrue(math.isfinite(got))
                            self.assertGreater(got, 0.0)

    def test_description_help_text(self):
        desc = OpenOptics_DepthTemporalSmooth.DESCRIPTION
        for word in ("metres", "spike", "missing", "Depth of Field"):
            self.assertIn(word, desc)

    def test_rejects_non_3d(self):
        with self.assertRaisesRegex(ValueError, "3-dimensional") as ctx:
            OpenOptics_DepthTemporalSmooth().smooth(torch.ones(4, 4), 0.7)
        self.assertIn("2 dimensions", str(ctx.exception))

    def test_rejects_2d_with_message(self):
        with self.assertRaisesRegex(ValueError, "3-dimensional"):
            OpenOptics_DepthTemporalSmooth().smooth(torch.ones(4, 4), 0.7)

    def test_rejects_bad_strength(self):
        depth = torch.ones(3, 4, 4)
        for bad in (2, -0.1, float("nan")):
            with self.assertRaisesRegex(ValueError, "strength"):
                OpenOptics_DepthTemporalSmooth().smooth(depth, bad)

    def test_single_frame_unchanged(self):
        g = torch.Generator().manual_seed(2)
        depth = (torch.rand(1, 5, 5, generator=g) * 5.0 + 1.0).to(torch.float32)
        for strength in (0.7, 1.0):
            (out,) = OpenOptics_DepthTemporalSmooth().smooth(depth, strength)
            self.assertEqual(tuple(out.shape), (1, 5, 5))
            for a, b in zip(out.flatten().tolist(), depth.flatten().tolist()):
                self.assertAlmostEqual(a, b, delta=1e-6)

    def _invalid_depth(self):
        g = torch.Generator().manual_seed(7)
        depth = (torch.rand(6, 8, 8, generator=g) * 4.0 + 2.0).to(torch.float32)
        bad = (float("nan"), float("inf"), float("-inf"), 0.0, -1.0)
        for i, v in enumerate(bad):
            depth[0, i, i] = v
            depth[2 + i % 4, i + 1, 7 - i] = v
        depth[5, 3, 3] = float("nan")
        return depth

    def test_invalid_values_never_reach_output(self):
        depth = self._invalid_depth()
        (out,) = OpenOptics_DepthTemporalSmooth().smooth(depth, 0.7)
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(out.device.type, "cpu")
        self.assertEqual(tuple(out.shape), (6, 8, 8))
        self.assertTrue(torch.isfinite(out).all())
        self.assertTrue((out > 0).all())
        self.assertNotEqual(out.data_ptr(), depth.data_ptr())

    def test_invalid_values_large_tensor(self):
        g = torch.Generator().manual_seed(8)
        depth = (torch.rand(4, 64, 64, generator=g) * 4.0 + 2.0).to(torch.float32)
        bad = (float("nan"), float("inf"), float("-inf"), 0.0, -1.0)
        for k in range(200):
            depth[k % 4, (k * 7) % 64, (k * 13) % 64] = bad[k % 5]
        (out,) = OpenOptics_DepthTemporalSmooth().smooth(depth, 0.7)
        self.assertEqual(tuple(out.shape), (4, 64, 64))
        self.assertTrue(torch.isfinite(out).all())
        self.assertTrue((out > 0).all())

    def test_chunk_frames_input_spec(self):
        spec = OpenOptics_DepthTemporalSmooth.INPUT_TYPES()["required"]["chunk_frames"]
        self.assertEqual(spec[0], "INT")
        self.assertEqual(spec[1]["default"], 8)
        self.assertEqual(spec[1]["min"], 1)

    def test_chunk_frames_zero_raises(self):
        with self.assertRaisesRegex(ValueError, "chunk_frames"):
            OpenOptics_DepthTemporalSmooth().smooth(torch.ones(3, 4, 4), 0.7, 0)

    def test_chunk_sizes_match_full(self):
        depth = self._invalid_depth()
        node = OpenOptics_DepthTemporalSmooth()
        (full,) = node.smooth(depth, 0.7, 8)
        for size in (1, 3):
            (out,) = node.smooth(depth, 0.7, size)
            self.assertEqual(out.device.type, "cpu")
            self.assertEqual(out.dtype, torch.float32)
            self.assertEqual(tuple(out.shape), (6, 8, 8))
            torch.testing.assert_close(out, full, rtol=0, atol=1e-5)

    def test_input_tensor_unchanged(self):
        depth = self._invalid_depth()
        clone = depth.clone()
        OpenOptics_DepthTemporalSmooth().smooth(depth, 0.7)
        torch.testing.assert_close(depth, clone, rtol=0, atol=0, equal_nan=True)


if __name__ == "__main__":
    unittest.main()
