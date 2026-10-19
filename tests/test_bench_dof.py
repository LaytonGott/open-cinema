import os
import unittest

import torch

from open_optics_nodes import OpenOptics_DepthOfField
from tests.bench_util import node_kwargs, record_result, run_bench
from tests.synth_frames import make_depth, make_frames


@unittest.skipUnless(os.environ.get("OPEN_OPTICS_BENCH") == "1", "set by npm run test:bench")
class TestBenchDepthOfField(unittest.TestCase):
    def tearDown(self):
        torch.cuda.empty_cache()

    def test_bench_depth_of_field(self):
        image = make_frames(121, 704, 1280)
        depth = make_depth(121, 704, 1280)
        kwargs = node_kwargs(OpenOptics_DepthOfField, image, depth)
        kwargs.update(focal_mm=50.0, f_number=2.0, focus_m=3.0, sensor_width_mm=36.0,
                      quality="normal", max_radius_px=32, colorspace="srgb")
        outputs, seconds, peak = run_bench(OpenOptics_DepthOfField, kwargs)
        print(f"Depth of Field, 121 frames at 1280x704: {seconds:.1f} s, "
              f"peak GPU memory {peak:.2f} GiB")
        record_result("OpenOptics_DepthOfField", 8, seconds, peak)
        out = outputs[0]
        self.assertLess(seconds, 30.0)
        self.assertLess(peak, 8.0)
        self.assertEqual(tuple(out.shape), (121, 704, 1280, 3))
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(out.device.type, "cpu")
        self.assertTrue(bool(torch.isfinite(out).all()))
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)
        self.assertGreater(float((out - image).abs().mean()), 0.003)


if __name__ == "__main__":
    unittest.main()
