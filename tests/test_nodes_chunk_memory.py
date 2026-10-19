"""DepthOfField: a smaller chunk_frames lowers the peak GPU memory."""

import os
import unittest
from unittest import mock

import torch

from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField


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


@unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
class TestChunkMemory(unittest.TestCase):
    def tearDown(self):
        torch.cuda.empty_cache()

    def _peak(self, image, depth, chunk_frames):
        cls = OpenOptics_DepthOfField
        kwargs = _kwargs(cls, image, depth)
        kwargs["chunk_frames"] = chunk_frames
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        outputs = getattr(cls(), cls.FUNCTION)(**kwargs)
        torch.cuda.synchronize()
        peak = torch.cuda.max_memory_allocated()
        del outputs
        return peak

    def test_smaller_chunk_lower_peak_memory(self):
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cuda"}):
            torch.manual_seed(0)
            image = torch.rand(64, 64, 64, 3, dtype=torch.float32)
            depth = torch.linspace(0.5, 8, 64).expand(64, 64, 64).contiguous()
            small = self._peak(image, depth, 1)
            large = self._peak(image, depth, 32)
        print(f"peak chunk_frames=1: {small}, chunk_frames=32: {large}")
        self.assertLess(small, large)


if __name__ == "__main__":
    unittest.main()
