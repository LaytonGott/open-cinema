import gc
import unittest
from unittest import mock

import torch

from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField


@unittest.skipUnless(torch.cuda.is_available(), "CUDA is not available")
class DepthOfFieldGpuReleaseTests(unittest.TestCase):
    def tearDown(self):
        gc.collect()
        torch.cuda.empty_cache()

    def test_memory_released_after_run(self):
        torch.manual_seed(0)
        image = torch.rand(4, 64, 64, 3)
        # 200 distinct depths in 0.8..8 m (metres), spread over the frame.
        depth = torch.linspace(0.8, 8.0, 200).repeat(4 * 64 * 64 // 200 + 1)[: 4 * 64 * 64]
        depth = depth.reshape(4, 64, 64)
        gc.collect()
        torch.cuda.empty_cache()
        start = torch.cuda.memory_allocated()
        torch.cuda.reset_peak_memory_stats()
        with mock.patch.dict("os.environ", {"OPEN_OPTICS_DEVICE": "cuda"}):
            out, coc = OpenOptics_DepthOfField().apply(
                image, focal_mm=50.0, f_number=1.8, focus_m=2.0,
                max_radius_px=24, depth_mask=depth)
        peak = torch.cuda.max_memory_allocated()
        del out, coc
        gc.collect()
        torch.cuda.empty_cache()
        self.assertLessEqual(torch.cuda.memory_allocated(), start)
        self.assertLess(peak, 1024 ** 3)


if __name__ == "__main__":
    unittest.main()
