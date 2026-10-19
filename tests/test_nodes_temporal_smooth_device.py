import os
import unittest
from pathlib import Path
from unittest import mock

import torch

from open_optics_nodes import temporal_torch


def _depth():
    gen = torch.Generator().manual_seed(7)
    return torch.rand(4, 8, 8, generator=gen, dtype=torch.float32) * 5.0 + 1.0


class TemporalSmoothDeviceTest(unittest.TestCase):
    def test_cpu(self):
        depth = _depth()
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cpu"}):
            result, used = temporal_torch.smooth_sequence_torch(
                depth, 0.7, 3, torch.device("cpu"))
        self.assertEqual(used.type, "cpu")
        self.assertEqual(result.device.type, "cpu")
        self.assertEqual(result.dtype, torch.float32)
        self.assertEqual(result.shape, depth.shape)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA not available")
    def test_cuda(self):
        depth = _depth()
        try:
            result, used = temporal_torch.smooth_sequence_torch(
                depth, 0.7, 3, torch.device("cuda"))
            self.assertEqual(str(used), "cuda:0")
            self.assertEqual(result.device.type, "cpu")
            self.assertEqual(result.dtype, torch.float32)
            self.assertEqual(result.shape, depth.shape)
        finally:
            torch.cuda.empty_cache()

    def test_reference_is_torch_free(self):
        path = Path(__file__).resolve().parent.parent / "open_optics" / "temporal.py"
        self.assertNotIn("torch", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
