"""Tensor contract and determinism tests shared by all seven nodes."""

import unittest

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS

B, H, W = 2, 24, 32


def _make_inputs():
    torch.manual_seed(1234)
    image = torch.rand(B, H, W, 3, dtype=torch.float32)
    depth = 0.5 + 7.5 * torch.rand(B, H, W, dtype=torch.float32)
    return image, depth


def _defaults(cls):
    out = {}
    for name, spec in cls.INPUT_TYPES()["required"].items():
        if spec[0] in ("IMAGE", "MASK"):
            continue
        if isinstance(spec[0], list):
            out[name] = spec[0][0]
        else:
            out[name] = spec[1]["default"]
    return out


def _call(cls, image, depth):
    kwargs = _defaults(cls)
    if "image" in cls.INPUT_TYPES()["required"]:
        kwargs["image"] = image
    if "depth_mask" in cls.INPUT_TYPES().get("optional", {}):
        kwargs["depth_mask"] = depth
    return getattr(cls(), cls.FUNCTION)(**kwargs)


class TestContract(unittest.TestCase):
    def _check_outputs(self, cls, outputs, batch, channels=3):
        self.assertEqual(len(outputs), len(cls.RETURN_TYPES))
        for kind, t in zip(cls.RETURN_TYPES, outputs):
            self.assertIsInstance(t, torch.Tensor)
            self.assertEqual(t.dtype, torch.float32)
            self.assertEqual(t.device.type, "cpu")
            self.assertTrue(bool(torch.isfinite(t).all()))
            if kind == "IMAGE":
                self.assertEqual(t.dim(), 4)
                self.assertEqual(t.shape[0], batch)
                self.assertEqual(t.shape[-1], channels)
                self.assertGreaterEqual(float(t.min()), 0.0)
                self.assertLessEqual(float(t.max()), 1.0)
            elif kind == "MASK":
                self.assertEqual(t.dim(), 3)
                self.assertEqual(t.shape[0], batch)

    def test_defaults_contract_and_determinism(self):
        image, depth = _make_inputs()
        for key, cls in NODE_CLASS_MAPPINGS.items():
            with self.subTest(node=key):
                first = _call(cls, image, depth)
                self._check_outputs(cls, first, B)
                second = _call(cls, image, depth)
                for a, b in zip(first, second):
                    self.assertTrue(torch.equal(a, b))

    def test_depth_to_metric_mask_shape(self):
        _, depth = _make_inputs()
        cls = NODE_CLASS_MAPPINGS["OpenOptics_DepthToMetric"]
        z, preview = _call(cls, None, depth)
        self.assertEqual(tuple(z.shape), (B, H, W))
        self.assertEqual(tuple(preview.shape), (B, H, W, 3))

    def test_single_frame_batch(self):
        image, depth = _make_inputs()
        for key, cls in NODE_CLASS_MAPPINGS.items():
            with self.subTest(node=key):
                out = _call(cls, image[:1], depth[:1])
                self._check_outputs(cls, out, 1)

    def test_four_channel_image(self):
        image, depth = _make_inputs()
        rgba = torch.cat([image, torch.rand(B, H, W, 1)], dim=-1)
        for key in ("OpenOptics_Vignette", "OpenOptics_ChromaticAberration"):
            cls = NODE_CLASS_MAPPINGS[key]
            with self.subTest(node=key):
                out = _call(cls, rgba, depth)
                self._check_outputs(cls, out, B, channels=4)


if __name__ == "__main__":
    unittest.main()
