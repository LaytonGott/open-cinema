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


if __name__ == "__main__":
    unittest.main()
