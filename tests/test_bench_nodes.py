import os
import unittest

import torch

import open_optics_nodes
from tests.bench_util import node_kwargs, record_result, run_bench
from tests.synth_frames import make_depth, make_frames


@unittest.skipUnless(os.environ.get("OPEN_OPTICS_BENCH") == "1", "set by npm run test:bench")
class TestBenchNodes(unittest.TestCase):
    def _bench(self, key):
        cls = open_optics_nodes.NODE_CLASS_MAPPINGS[key]
        image = make_frames(121, 704, 1280)
        depth = make_depth(121, 704, 1280)
        kwargs = node_kwargs(cls, image, depth)
        outputs, seconds, peak = run_bench(cls, kwargs)
        print(f"{key}, 121 frames at 1280x704: {seconds:.1f} s, peak GPU memory {peak:.2f} GiB")
        record_result(key, 8, seconds, peak)
        self.assertIsInstance(outputs, tuple)
        out = outputs[0]
        self.assertEqual(out.device.type, "cpu")
        self.assertEqual(out.dtype, torch.float32)
        self.assertTrue(bool(torch.isfinite(out).all()))
        torch.cuda.empty_cache()

    def test_bench_anamorphic(self):
        self._bench("OpenOptics_Anamorphic")

    def test_bench_chromatic_aberration(self):
        self._bench("OpenOptics_ChromaticAberration")

    def test_bench_focal_crop(self):
        self._bench("OpenOptics_FocalCrop")

    def test_bench_lens_distortion(self):
        self._bench("OpenOptics_LensDistortion")

    def test_bench_vignette(self):
        self._bench("OpenOptics_Vignette")

    def test_bench_depth_to_metric(self):
        self._bench("OpenOptics_DepthToMetric")

    def test_bench_depth_temporal_smooth(self):
        self._bench("OpenOptics_DepthTemporalSmooth")


if __name__ == "__main__":
    unittest.main()
