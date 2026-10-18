import unittest

import torch

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

    def test_rejects_non_3d(self):
        with self.assertRaises(ValueError):
            OpenOptics_DepthTemporalSmooth().smooth(torch.ones(4, 4), 0.7)


if __name__ == "__main__":
    unittest.main()
