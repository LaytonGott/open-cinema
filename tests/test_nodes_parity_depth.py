import os
import unittest

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS


class TestCpuGpuParityDepth(unittest.TestCase):
    def setUp(self):
        self._old_device = os.environ.get("OPEN_OPTICS_DEVICE")
        torch.manual_seed(5)
        self.depth = torch.rand(6, 32, 32) + 0.1

    def tearDown(self):
        if self._old_device is None:
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
        else:
            os.environ["OPEN_OPTICS_DEVICE"] = self._old_device
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _parity(self, name, input_name, **kwargs):
        cls = NODE_CLASS_MAPPINGS[name]
        outs = {}
        for dev in ("cpu", "cuda"):
            os.environ["OPEN_OPTICS_DEVICE"] = dev
            outs[dev] = getattr(cls(), cls.FUNCTION)(
                **{input_name: self.depth.clone()}, chunk_frames=2, **kwargs
            )
        self.assertEqual(len(outs["cpu"]), len(outs["cuda"]))
        for a, b in zip(outs["cpu"], outs["cuda"]):
            self.assertEqual(a.device.type, "cpu")
            self.assertEqual(b.device.type, "cpu")
            self.assertEqual(a.shape, b.shape)
            self.assertLess((a - b).abs().max().item(), 1e-4)
        return outs["cpu"]

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_depth_to_metric_parity(self):
        self._parity("OpenOptics_DepthToMetric", "depth_mask", near_m=0.5, far_m=10.0)
        self._parity(
            "OpenOptics_DepthToMetric", "depth_mask", near_m=0.5, far_m=10.0,
            inverse_depth=False, low_percentile=5.0, high_percentile=95.0,
        )

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_depth_temporal_smooth_parity(self):
        outs = self._parity("OpenOptics_DepthTemporalSmooth", "depth", strength=0.7)
        self.assertFalse(torch.equal(outs[0], self.depth))


if __name__ == "__main__":
    unittest.main()
