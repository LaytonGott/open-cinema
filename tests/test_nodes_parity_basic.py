import os
import unittest

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS


class TestCpuGpuParityBasic(unittest.TestCase):
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

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_anamorphic_parity(self):
        self._parity("OpenOptics_Anamorphic", squeeze=1.5)

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_chromatic_aberration_parity(self):
        self._parity("OpenOptics_ChromaticAberration", ca_r=0.01, ca_b=-0.01)

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_focal_crop_parity(self):
        self._parity("OpenOptics_FocalCrop", source_focal_mm=24.0, target_focal_mm=50.0)


if __name__ == "__main__":
    unittest.main()
