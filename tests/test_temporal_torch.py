import inspect
import unittest

import torch

from open_optics.temporal import smooth_depth_sequence
from open_optics_nodes.temporal_torch import smooth_sequence_torch


def _make_depth():
    gen = torch.Generator().manual_seed(7)
    depth = 1.0 + 4.0 * torch.rand(9, 6, 6, generator=gen)
    depth[2, 0, 0] = float("nan")
    depth[3, 0, 1] = 0.0
    depth[4, 0, 2] = -2.0
    depth[5, 1, 0] = depth[4, 1, 0] * 10.0  # one-frame spike
    depth[5:, 1, 1] = depth[4, 1, 1] * 4.0  # persistent step
    depth[:, 2, 2] = float("nan")  # never valid
    depth[:4, 3, 3] = float("nan")  # first valid at frame 4
    depth[:4, 3, 4] = -1.0
    return depth


class SmoothSequenceTorchTest(unittest.TestCase):
    def _check(self, device, device_type):
        depth = _make_depth()
        for chunk_frames in (1, 3, 9):
            for strength in (0.0, 0.7, 1.0):
                with self.subTest(chunk_frames=chunk_frames, strength=strength):
                    result, used = smooth_sequence_torch(depth, strength, chunk_frames, device)
                    ref = torch.tensor(
                        smooth_depth_sequence(depth.double().tolist(), strength),
                        dtype=torch.float64,
                    )
                    self.assertEqual(result.dtype, torch.float32)
                    self.assertEqual(result.device.type, "cpu")
                    self.assertEqual(used.type, device_type)
                    got = result.double()
                    self.assertTrue(torch.equal(torch.isnan(got), torch.isnan(ref)))
                    ok = ~torch.isnan(ref)
                    self.assertLessEqual((got[ok] - ref[ok]).abs().max().item(), 1e-4)

    def test_matches_reference_cpu(self):
        self._check(torch.device("cpu"), "cpu")

    def test_source_has_no_tolist_or_item(self):
        from open_optics_nodes import temporal_torch

        for fn in (temporal_torch.smooth_sequence_torch, temporal_torch._update_frame):
            src = inspect.getsource(fn)
            self.assertNotIn(".tolist(", src)
            self.assertNotIn(".item(", src)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA not available")
    def test_matches_reference_cuda(self):
        try:
            self._check(torch.device("cuda"), "cuda")
        finally:
            torch.cuda.empty_cache()


if __name__ == "__main__":
    unittest.main()
