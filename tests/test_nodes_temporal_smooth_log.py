"""Depth Temporal Smooth logs one INFO record with the device it used."""

import os
import re
import unittest
from unittest import mock

import torch

from open_optics_nodes.depth_temporal_smooth import OpenOptics_DepthTemporalSmooth

B, H, W = 5, 8, 8
CHUNK = 2


def _depth():
    torch.manual_seed(3)
    return 0.5 + 7.5 * torch.rand(B, H, W, dtype=torch.float32)


class TestTemporalSmoothLog(unittest.TestCase):
    def _run(self, device_env):
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": device_env}), \
                self.assertLogs("open_optics_nodes", "INFO") as logs:
            result = OpenOptics_DepthTemporalSmooth().smooth(_depth(), chunk_frames=CHUNK)
        self.assertEqual(len(logs.records), 1)
        return logs.records[0].getMessage(), result

    def test_log_record_on_cpu(self):
        message, _ = self._run("cpu")
        self.assertRegex(
            message,
            r"^node=OpenOptics_DepthTemporalSmooth device=cpu frames=5 "
            r"chunk_frames=2 seconds=\d+\.\d{3}$")

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is not available")
    def test_log_record_on_cuda(self):
        try:
            message, result = self._run("cuda")
            self.assertIn("device=cuda:0", message)
            out = result[0]
            self.assertEqual(out.device.type, "cpu")
            self.assertEqual(out.dtype, torch.float32)
        finally:
            torch.cuda.empty_cache()


if __name__ == "__main__":
    unittest.main()
