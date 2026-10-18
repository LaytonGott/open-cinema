import unittest

import torch

from open_optics import anamorphic
from open_optics_nodes.anamorphic import OpenOptics_Anamorphic


class TestAnamorphicNode(unittest.TestCase):
    def setUp(self):
        self.img = torch.rand(1, 20, 30, 3, dtype=torch.float32)
        self.node = OpenOptics_Anamorphic()

    def test_desqueeze_widens(self):
        out = self.node.apply(self.img, 2.0, "desqueeze")[0]
        self.assertEqual(tuple(out.shape), (1, 20, 60, 3))

    def test_squeeze_inverts(self):
        wide = self.node.apply(self.img, 2.0, "desqueeze")[0]
        out = self.node.apply(wide, 2.0, "squeeze")[0]
        w, h = anamorphic.squeeze_size(60, 20, 2.0)
        self.assertEqual(tuple(out.shape), (1, round(h), round(w), 3))

    def test_keep_width_shortens(self):
        out = self.node.apply(self.img, 2.0, "desqueeze", True)[0]
        self.assertEqual(tuple(out.shape), (1, 10, 30, 3))

    def test_squeeze_one_identity(self):
        out = self.node.apply(self.img, 1.0)[0]
        self.assertTrue(torch.allclose(out, self.img, atol=1e-6))

    def test_below_one_raises(self):
        with self.assertRaises(ValueError):
            self.node.apply(self.img, 0.9)

    def test_error_messages_name_inputs(self):
        img = torch.zeros(1, 8, 8, 3, dtype=torch.float32)
        with self.assertRaises(ValueError) as ctx:
            self.node.apply(img, 0.5)
        self.assertIn("squeeze", str(ctx.exception))
        self.assertIn("0.5", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            self.node.apply(img, float("nan"))
        self.assertIn("squeeze", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            self.node.apply(img, 2.0, "bogus")
        self.assertIn("mode", str(ctx.exception))

    def test_desqueeze_values_within_tolerance(self):
        img = torch.full((1, 20, 30, 3), 0.5, dtype=torch.float32)
        out = self.node.apply(img, 2.0, "desqueeze")[0]
        self.assertAlmostEqual(float(out.min()), 0.5, delta=1e-5)
        self.assertAlmostEqual(float(out.max()), 0.5, delta=1e-5)
        self.assertEqual(out.shape[2], round(30 * 2.0))


class TestAnamorphicAcceptanceSizes(unittest.TestCase):
    def setUp(self):
        self.img = torch.rand(1, 48, 64, 3)
        self.node = OpenOptics_Anamorphic()

    def test_desqueeze_widens(self):
        out = self.node.apply(self.img, 2.0, "desqueeze")[0]
        self.assertEqual(tuple(out.shape), (1, 48, 128, 3))

    def test_squeeze_narrows(self):
        out = self.node.apply(self.img, 2.0, "squeeze")[0]
        self.assertEqual(tuple(out.shape), (1, 48, 32, 3))

    def test_keep_width_desqueeze(self):
        out = self.node.apply(self.img, 2.0, "desqueeze", True)[0]
        self.assertEqual(tuple(out.shape), (1, 24, 64, 3))

    def test_keep_width_squeeze(self):
        out = self.node.apply(self.img, 2.0, "squeeze", True)[0]
        self.assertEqual(tuple(out.shape), (1, 96, 64, 3))

    def test_default_squeeze(self):
        spec = OpenOptics_Anamorphic.INPUT_TYPES()["required"]["squeeze"]
        self.assertEqual(spec[1]["default"], 1.33)

    def test_output_dtype_and_range(self):
        out = self.node.apply(self.img, 2.0, "desqueeze")[0]
        self.assertEqual(out.dtype, torch.float32)
        self.assertGreaterEqual(out.min().item(), 0.0)
        self.assertLessEqual(out.max().item(), 1.0)


class TestAnamorphicNonPositive(unittest.TestCase):
    def test_nonpositive_squeeze_raises(self):
        img = torch.zeros(1, 8, 8, 3)
        node = OpenOptics_Anamorphic()
        for squeeze in (0.0, -1.0):
            with self.assertRaises(ValueError) as ctx:
                node.apply(img, squeeze)
            self.assertIn("squeeze", str(ctx.exception))


class TestAnamorphicRoundTrip(unittest.TestCase):
    def test_round_trip_smooth_image(self):
        ys, xs = torch.meshgrid(torch.arange(32), torch.arange(32), indexing="ij")
        ramp = ((xs + ys).to(torch.float32) / 62.0)
        img = ramp.reshape(1, 32, 32, 1).expand(1, 32, 32, 3).contiguous()
        node = OpenOptics_Anamorphic()
        wide = node.apply(img, 2.0, "desqueeze")[0]
        out = node.apply(wide, 2.0, "squeeze")[0]
        self.assertEqual(tuple(out.shape), (1, 32, 32, 3))
        # bilinear resizing a linear ramp is exact except in the edge columns,
        # where clamping to the border causes an error of 0.125 ramp pixels
        # = 0.125/62 = 0.002; 0.003 allows float error.
        self.assertLessEqual(float((out - img).abs().max()), 0.003)


class TestAnamorphicMinSize(unittest.TestCase):
    def test_one_pixel_minimum(self):
        img = torch.rand(1, 1, 1, 3)
        # library height 1/4 = 0.25 rounds to 0 and is raised to 1
        out = OpenOptics_Anamorphic().apply(img, 4.0, "desqueeze", True)[0]
        self.assertEqual(tuple(out.shape), (1, 1, 1, 3))


if __name__ == "__main__":
    unittest.main()
