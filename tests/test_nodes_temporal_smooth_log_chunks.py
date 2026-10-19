"""The Depth Temporal Smooth log record reports the chunk size used."""

import re
import unittest
from unittest import mock

import torch

from open_optics_nodes.depth_temporal_smooth import OpenOptics_DepthTemporalSmooth


def _depth():
    gen = torch.Generator().manual_seed(0)
    return (torch.rand(5, 8, 8, generator=gen) * 7.5 + 0.5).to(torch.float32)


class TemporalSmoothLogChunksTest(unittest.TestCase):
    def _check(self, device_env, device_name):
        depth = _depth()
        for c in (1, 3, 5):
            with mock.patch.dict("os.environ", {"OPEN_OPTICS_DEVICE": device_env}):
                with self.assertLogs("open_optics_nodes", "INFO") as cm:
                    OpenOptics_DepthTemporalSmooth().smooth(depth, 0.7, chunk_frames=c)
            self.assertEqual(len(cm.records), 1)
            pattern = (
                r"^node=OpenOptics_DepthTemporalSmooth device=%s frames=5 "
                r"chunk_frames=%d seconds=\d+\.\d{3}$" % (re.escape(device_name), c)
            )
            self.assertRegex(cm.records[0].getMessage(), pattern)

    def test_cpu(self):
        self._check("cpu", "cpu")

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA not available")
    def test_cuda(self):
        try:
            self._check("cuda", "cuda:0")
        finally:
            torch.cuda.empty_cache()


if __name__ == "__main__":
    unittest.main()
