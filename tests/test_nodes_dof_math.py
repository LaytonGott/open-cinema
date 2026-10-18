import unittest

import torch

from open_optics_nodes.dof_math import coc_radius_map


class CocRadiusMapTest(unittest.TestCase):
    def test_in_focus_is_zero(self):
        depth = torch.full((1, 4, 64), 3.0)
        out = coc_radius_map(depth, 50, 2.8, 3.0, 36, 100)
        self.assertEqual(out.abs().max().item(), 0.0)

    def test_known_value(self):
        # 2500 / (2.8 * 2950) * 0.5 mm = 0.151332 mm; * 64 / 36 / 2
        depth = torch.full((1, 2, 64), 3.0)
        depth[0, 0, 0] = 6.0
        out = coc_radius_map(depth, 50, 2.8, 3.0, 36, 100)
        self.assertAlmostEqual(out[0, 0, 0].item(), 0.134517, delta=1e-5)

    def test_cap(self):
        depth = torch.full((1, 2, 64), 6.0)
        out = coc_radius_map(depth, 50, 2.8, 3.0, 36, 0.1)
        self.assertAlmostEqual(out[0, 0, 0].item(), 0.1, delta=1e-6)

    def test_dtype(self):
        out = coc_radius_map(torch.full((1, 2, 8), 2.0, dtype=torch.float64), 50, 2.8, 3.0, 36, 10)
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(out.shape, (1, 2, 8))


if __name__ == "__main__":
    unittest.main()
