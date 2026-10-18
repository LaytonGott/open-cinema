import unittest

import torch

from open_optics import chromatic
from open_optics_nodes import NODE_CLASS_MAPPINGS
from open_optics_nodes.chromatic_aberration import OpenOptics_ChromaticAberration


class ChromaticAberrationNodeTest(unittest.TestCase):
    def test_registered(self):
        self.assertIs(NODE_CLASS_MAPPINGS["OpenOptics_ChromaticAberration"], OpenOptics_ChromaticAberration)

    def test_zero_identity(self):
        img = torch.rand(1, 12, 10, 3)
        out = OpenOptics_ChromaticAberration().apply(img, 0.0, 0.0)[0]
        self.assertTrue(torch.equal(out, img))

    def test_red_shift_at_16px(self):
        # Red and green are horizontal ramps equal to the x pixel index / 32.
        x = torch.arange(33, dtype=torch.float32)
        img = torch.zeros(1, 33, 33, 3)
        img[..., 0] = (x / 32.0).reshape(1, 1, 33)
        img[..., 1] = (x / 32.0).reshape(1, 1, 33)
        ca = 0.05
        out = OpenOptics_ChromaticAberration().apply(img, ca, 0.0)[0]
        # Pixel x=32 is 16 px right of centre; the library shift there is 0.8 px,
        # and the output samples the source at 16 / 1.05 from the centre.
        (rdx, _), _ = chromatic.fringe_shift_px(32, 16, 33, 33, red=ca)
        scale = chromatic.channel_scales(ca, 0.0)[0]
        self.assertAlmostEqual(rdx, 0.8, delta=1e-9)
        src_x = 16 + 16 / scale
        self.assertAlmostEqual(out[0, 16, 32, 0].item() * 32.0, src_x, delta=0.05)
        # Green and blue unchanged.
        self.assertTrue(torch.equal(out[..., 1], img[..., 1]))
        self.assertTrue(torch.equal(out[..., 2], img[..., 2]))


if __name__ == "__main__":
    unittest.main()
