"""Every node: chunk_frames spec, CPU in/out, inputs left intact, no GPU leak."""

import os
import unittest

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS


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


def _kwargs(cls, image, depth):
    kwargs = _defaults(cls)
    types = cls.INPUT_TYPES()
    if "image" in types["required"]:
        kwargs["image"] = image
    if "depth" in types["required"]:
        kwargs["depth"] = depth
    if "depth_mask" in types.get("optional", {}):
        kwargs["depth_mask"] = depth
    return kwargs


class TestNodesChunked(unittest.TestCase):
    def tearDown(self):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def test_covers_eight_nodes(self):
        self.assertEqual(len(NODE_CLASS_MAPPINGS), 8)

    def test_chunk_frames_spec(self):
        for key, cls in NODE_CLASS_MAPPINGS.items():
            types = cls.INPUT_TYPES()
            spec = (types["required"].get("chunk_frames")
                    or types["optional"]["chunk_frames"])
            self.assertEqual(spec[0], "INT", key)
            self.assertEqual(spec[1]["default"], 8, key)
            self.assertEqual(spec[1]["min"], 1, key)

    def test_chunk_frames_zero_raises(self):
        torch.manual_seed(3)
        image = torch.rand(5, 32, 32, 3, dtype=torch.float32)
        depth = 0.5 + 7.5 * torch.rand(5, 32, 32, dtype=torch.float32)
        for key, cls in NODE_CLASS_MAPPINGS.items():
            kwargs = _kwargs(cls, image, depth)
            kwargs["chunk_frames"] = 0
            with self.assertRaises(ValueError, msg=key):
                getattr(cls(), cls.FUNCTION)(**kwargs)

    def _run(self, device):
        old = os.environ.get("OPEN_OPTICS_DEVICE")
        os.environ["OPEN_OPTICS_DEVICE"] = device
        try:
            torch.manual_seed(5)
            image = torch.rand(5, 32, 32, 3, dtype=torch.float32)
            depth = 0.5 + 7.5 * torch.rand(5, 32, 32, dtype=torch.float32)
            for key, cls in NODE_CLASS_MAPPINGS.items():
                kwargs = _kwargs(cls, image, depth)
                kwargs["chunk_frames"] = 2
                before_inputs = {
                    k: v.clone() for k, v in kwargs.items() if torch.is_tensor(v)
                }
                if device == "cuda":
                    torch.cuda.synchronize()
                    before = torch.cuda.memory_allocated()
                outputs = getattr(cls(), cls.FUNCTION)(**kwargs)
                for t in outputs:
                    self.assertEqual(t.device.type, "cpu", key)
                    self.assertEqual(t.dtype, torch.float32, key)
                del outputs
                for k, v in before_inputs.items():
                    self.assertTrue(torch.equal(kwargs[k], v), f"{key}: {k} changed")
                if device == "cuda":
                    torch.cuda.synchronize()
                    self.assertEqual(torch.cuda.memory_allocated(), before, key)
        finally:
            if old is None:
                os.environ.pop("OPEN_OPTICS_DEVICE", None)
            else:
                os.environ["OPEN_OPTICS_DEVICE"] = old

    def test_cpu(self):
        self._run("cpu")

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_cuda(self):
        self._run("cuda")


if __name__ == "__main__":
    unittest.main()
