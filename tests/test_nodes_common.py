import unittest

import torch

from open_optics_nodes import common


class NodesCommonTest(unittest.TestCase):
    def test_srgb_decode_half(self):
        # ((0.5 + 0.055) / 1.055) ** 2.4 = 0.2140411
        out = common.srgb_to_linear_t(torch.tensor([0.5]))
        self.assertAlmostEqual(out.item(), 0.2140411, delta=1e-5)

    def test_round_trip(self):
        x = torch.linspace(0, 1, 101)
        back = common.linear_to_srgb_t(common.srgb_to_linear_t(x))
        self.assertLess((back - x).abs().max().item(), 1e-5)

    def test_check_image_rejects_3d(self):
        with self.assertRaises(ValueError):
            common.check_image(torch.zeros(4, 4, 3))

    def test_check_image_accepts_4d(self):
        img = torch.zeros(1, 4, 4, 3)
        self.assertIs(common.check_image(img), img)

    def test_colorspace_invalid(self):
        with self.assertRaises(ValueError):
            common.to_linear(torch.zeros(1, 1, 1, 3), "hsv")
        with self.assertRaises(ValueError):
            common.from_linear(torch.zeros(1, 1, 1, 3), "hsv")

    def test_finish_clamps(self):
        out = common.finish(torch.tensor([1.5, -1.0, float("nan")]))
        self.assertAlmostEqual(out[0].item(), 1.0, places=6)
        self.assertAlmostEqual(out[1].item(), 0.0, places=6)
        self.assertAlmostEqual(out[2].item(), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
