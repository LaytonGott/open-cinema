"""With OPEN_OPTICS_DEVICE=cpu, no node allocates any GPU memory."""

import unittest
from unittest import mock

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


@unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
class TestNodesCpuNoGpuMemory(unittest.TestCase):
    def tearDown(self):
        torch.cuda.empty_cache()

    def test_cpu_mode_uses_no_gpu_memory(self):
        self.assertEqual(len(NODE_CLASS_MAPPINGS), 8)
        torch.manual_seed(7)
        image = torch.rand(3, 32, 32, 3, dtype=torch.float32)
        depth = 0.5 + 7.5 * torch.rand(3, 32, 32, dtype=torch.float32)
        with mock.patch.dict("os.environ", {"OPEN_OPTICS_DEVICE": "cpu"}):
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            peak_before = torch.cuda.max_memory_allocated()
            alloc_before = torch.cuda.memory_allocated()
            for key, cls in NODE_CLASS_MAPPINGS.items():
                kwargs = _kwargs(cls, image, depth)
                kwargs["chunk_frames"] = 2
                outputs = getattr(cls(), cls.FUNCTION)(**kwargs)
                del outputs
            torch.cuda.synchronize()
            self.assertEqual(torch.cuda.max_memory_allocated(), peak_before)
            self.assertEqual(torch.cuda.memory_allocated(), alloc_before)


if __name__ == "__main__":
    unittest.main()
