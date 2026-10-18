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

    def test_defaults_are_zero(self):
        req = OpenOptics_ChromaticAberration.INPUT_TYPES()["required"]
        self.assertEqual(req["ca_r"][1]["default"], 0.0)
        self.assertEqual(req["ca_b"][1]["default"], 0.0)
        img = torch.rand(1, 12, 10, 3)
        out = OpenOptics_ChromaticAberration().apply(img)[0]
        self.assertTrue(torch.equal(out, img))

    def test_blue_shift_at_8px(self):
        # Tolerance: delta 0.05 in ramp-pixel units (bilinear sampling of a linear ramp).
        x = torch.arange(33, dtype=torch.float32)
        ramp = (x / 32.0).reshape(1, 1, 33)
        img = torch.zeros(1, 33, 33, 3)
        for c in range(3):
            img[..., c] = ramp
        ca = -0.05
        out = OpenOptics_ChromaticAberration().apply(img, 0.0, ca)[0]
        scale = chromatic.channel_scales(0.0, ca)[1]
        self.assertAlmostEqual(scale, 0.95, delta=1e-9)
        # x=24 is 8 px right of centre; output samples source at 16 + 8 / 0.95 = 24.421.
        self.assertAlmostEqual(out[0, 16, 24, 2].item() * 32.0, 16 + 8 / scale, delta=0.05)
        self.assertTrue(torch.equal(out[..., 0], img[..., 0]))
        self.assertTrue(torch.equal(out[..., 1], img[..., 1]))

    def test_red_opposite_signs(self):
        x = torch.arange(33, dtype=torch.float32)
        ramp = (x / 32.0).reshape(1, 1, 33)
        img = torch.zeros(1, 33, 33, 3)
        for c in range(3):
            img[..., c] = ramp
        out_pos = OpenOptics_ChromaticAberration().apply(img, 0.05, 0.0)[0]
        out_neg = OpenOptics_ChromaticAberration().apply(img, -0.05, 0.0)[0]
        # Output samples source at r / scale: 8 / 1.05 px (nearer centre) or 8 / 0.95 px.
        self.assertLess(out_pos[0, 16, 24, 0].item(), img[0, 16, 24, 0].item())
        self.assertGreater(out_neg[0, 16, 24, 0].item(), img[0, 16, 24, 0].item())
        self.assertTrue(torch.equal(out_pos[..., 1], img[..., 1]))
        self.assertTrue(torch.equal(out_neg[..., 1], img[..., 1]))

    def test_blue_opposite_signs(self):
        x = torch.arange(33, dtype=torch.float32)
        ramp = (x / 32.0).reshape(1, 1, 33)
        img = torch.zeros(1, 33, 33, 3)
        for c in range(3):
            img[..., c] = ramp
        out_pos = OpenOptics_ChromaticAberration().apply(img, 0.0, 0.05)[0]
        out_neg = OpenOptics_ChromaticAberration().apply(img, 0.0, -0.05)[0]
        # Output samples source at r / scale: nearer centre for +, farther for -.
        self.assertLess(out_pos[0, 16, 24, 2].item(), img[0, 16, 24, 2].item())
        self.assertGreater(out_neg[0, 16, 24, 2].item(), img[0, 16, 24, 2].item())
        self.assertTrue(torch.equal(out_pos[..., 0], img[..., 0]))
        self.assertTrue(torch.equal(out_neg[..., 0], img[..., 0]))

    def test_alpha_channel_kept(self):
        img = torch.rand(1, 12, 10, 4)
        out = OpenOptics_ChromaticAberration().apply(img, 0.05, 0.0)[0]
        self.assertTrue(torch.equal(out[..., 3], img[..., 3]))


if __name__ == "__main__":
    unittest.main()
