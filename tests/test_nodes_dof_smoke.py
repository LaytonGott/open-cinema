import unittest

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField
from open_optics_nodes.dof_math import coc_radius_map


def _image():
    g = torch.Generator().manual_seed(0)
    return torch.rand(1, 8, 8, 3, generator=g)


class TestDepthOfFieldSmoke(unittest.TestCase):
    def test_in_focus_is_identity(self):
        img = _image()
        depth = torch.full((1, 8, 8), 3.0)
        out, coc = OpenOptics_DepthOfField().apply(img, focus_m=3.0, depth_mask=depth)
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(tuple(out.shape), (1, 8, 8, 3))
        self.assertTrue(torch.allclose(out, img, atol=1e-4))
        self.assertEqual(tuple(coc.shape), (1, 8, 8))
        self.assertTrue(bool((coc == 0).all()))

    def test_far_depth_coc(self):
        img = _image()
        depth = torch.full((1, 8, 8), 10.0)
        _, coc = OpenOptics_DepthOfField().apply(img, depth_mask=depth, max_radius_px=16)
        expected = coc_radius_map(depth, 50.0, 2.8, 3.0, 36.0, 16) / 16
        self.assertGreater(float(expected[0, 0, 0]), 0.0)
        self.assertTrue(torch.allclose(coc, expected.clamp(0, 1), atol=1e-6))
        self.assertTrue(bool((coc == coc[0, 0, 0]).all()))

    def test_depth_input_count(self):
        img = _image()
        node = OpenOptics_DepthOfField()
        with self.assertRaises(ValueError):
            node.apply(img)
        with self.assertRaises(ValueError):
            node.apply(img, depth_mask=torch.ones(1, 8, 8),
                       depth_image=torch.ones(1, 8, 8, 3))

    def test_registration(self):
        self.assertIs(NODE_CLASS_MAPPINGS["OpenOptics_DepthOfField"], OpenOptics_DepthOfField)
        self.assertEqual(NODE_DISPLAY_NAME_MAPPINGS["OpenOptics_DepthOfField"],
                         "Open Optics: Depth of Field")


if __name__ == "__main__":
    unittest.main()
