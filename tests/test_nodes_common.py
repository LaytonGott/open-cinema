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

    def test_resolve_depth_needs_exactly_one(self):
        img = torch.zeros(1, 4, 4, 3)
        with self.assertRaisesRegex(ValueError, "Exactly one of depth_mask or depth_image"):
            common.resolve_depth(img)
        with self.assertRaisesRegex(ValueError, "Exactly one of depth_mask or depth_image"):
            common.resolve_depth(img, torch.ones(1, 4, 4), torch.ones(1, 4, 4, 3))

    def test_resolve_depth_size_and_batch_mismatch(self):
        img = torch.zeros(2, 4, 4, 3)
        with self.assertRaises(ValueError):
            common.resolve_depth(img, depth_mask=torch.ones(2, 4, 5))
        with self.assertRaises(ValueError):
            common.resolve_depth(img, depth_mask=torch.ones(1, 4, 4))

    def test_resolve_depth_grey_image_equals_mask(self):
        img = torch.zeros(1, 4, 4, 3)
        from_mask = common.resolve_depth(img, depth_mask=torch.full((1, 4, 4), 3.0))
        from_img = common.resolve_depth(img, depth_image=torch.full((1, 4, 4, 3), 3.0))
        self.assertTrue(torch.equal(from_mask, from_img))
        self.assertEqual(from_img.dtype, torch.float32)
        self.assertEqual(from_img[0, 0, 0].item(), 3.0)
        self.assertEqual(common.resolve_depth(None, depth_mask=torch.ones(1, 2, 2)).shape, (1, 2, 2))


if __name__ == "__main__":
    unittest.main()
