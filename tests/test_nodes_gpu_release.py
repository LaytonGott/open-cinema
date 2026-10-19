"""After a node call on the GPU, no device memory stays allocated."""

import gc
import unittest
from unittest import mock

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS
from tests.bench_util import node_kwargs


def _run(cls, image, depth):
    kwargs = node_kwargs(cls, image, depth)
    kwargs["chunk_frames"] = 2
    outputs = getattr(cls(), cls.FUNCTION)(**kwargs)
    del outputs


def _settle():
    gc.collect()
    torch.cuda.synchronize()
    torch.cuda.empty_cache()


@unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
class TestNodesGpuRelease(unittest.TestCase):
    def tearDown(self):
        torch.cuda.empty_cache()

    def test_nodes_free_gpu_memory(self):
        torch.manual_seed(7)
        image = torch.rand(3, 32, 32, 3, dtype=torch.float32)
        depth = 0.5 + 7.5 * torch.rand(3, 32, 32, dtype=torch.float32)
        with mock.patch.dict("os.environ", {"OPEN_OPTICS_DEVICE": "cuda"}):
            for key, cls in NODE_CLASS_MAPPINGS.items():
                with self.subTest(node=key):
                    # Warm-up so library workspaces are not counted as leaks.
                    _run(cls, image, depth)
                    _settle()
                    before = torch.cuda.memory_allocated()
                    _run(cls, image, depth)
                    _settle()
                    self.assertEqual(torch.cuda.memory_allocated(), before)


if __name__ == "__main__":
    unittest.main()
