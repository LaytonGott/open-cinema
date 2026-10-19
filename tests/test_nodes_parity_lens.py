import os
import unittest

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS


class TestCpuGpuParityLens(unittest.TestCase):
    def setUp(self):
        self._old_device = os.environ.get("OPEN_OPTICS_DEVICE")
        torch.manual_seed(5)
        self.image = torch.rand(5, 32, 32, 3)

    def tearDown(self):
        if self._old_device is None:
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
        else:
            os.environ["OPEN_OPTICS_DEVICE"] = self._old_device
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _parity(self, name, **kwargs):
        cls = NODE_CLASS_MAPPINGS[name]
        outs = {}
        for dev in ("cpu", "cuda"):
            os.environ["OPEN_OPTICS_DEVICE"] = dev
            outs[dev] = getattr(cls(), cls.FUNCTION)(
                image=self.image.clone(), chunk_frames=2, **kwargs
            )
        self.assertEqual(len(outs["cpu"]), len(outs["cuda"]))
        for a, b in zip(outs["cpu"], outs["cuda"]):
            self.assertEqual(a.device.type, "cpu")
            self.assertEqual(b.device.type, "cpu")
            self.assertEqual(a.shape, b.shape)
            self.assertLess((a - b).abs().max().item(), 1e-4)
        return outs["cpu"][0]

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_lens_distortion_parity(self):
        out = self._parity(
            "OpenOptics_LensDistortion",
            focal_mm=24.0, k1=-0.2, k2=0.05, p1=0.01, p2=-0.01,
        )
        self.assertGreater((out - self.image).abs().max().item(), 1e-3)

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_vignette_parity(self):
        self._parity("OpenOptics_Vignette", focal_mm=35.0, strength=1.0)

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_vignette_linear_parity(self):
        self._parity(
            "OpenOptics_Vignette", focal_mm=35.0, strength=1.0, colorspace="linear"
        )


if __name__ == "__main__":
    unittest.main()
