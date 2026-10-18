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


if __name__ == "__main__":
    unittest.main()
