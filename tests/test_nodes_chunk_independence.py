import os
import unittest

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS


class TestPerFrameChunkIndependence(unittest.TestCase):
    def setUp(self):
        self._old_device = os.environ.get("OPEN_OPTICS_DEVICE")
        os.environ["OPEN_OPTICS_DEVICE"] = "cpu"
        torch.manual_seed(11)
        self.image = torch.rand(7, 24, 32, 3)

    def tearDown(self):
        if self._old_device is None:
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
        else:
            os.environ["OPEN_OPTICS_DEVICE"] = self._old_device

    def _run(self, cls, **kwargs):
        return getattr(cls(), cls.FUNCTION)(**kwargs)

    def _check(self, name, **kwargs):
        cls = NODE_CLASS_MAPPINGS[name]
        ref = self._run(cls, image=self.image, chunk_frames=7, **kwargs)
        for chunk in (1, 3, 7):
            out = self._run(cls, image=self.image, chunk_frames=chunk, **kwargs)
            self.assertEqual(len(out), len(ref))
            for a, b in zip(out, ref):
                self.assertEqual(a.shape, b.shape)
                self.assertLess((a - b).abs().max().item(), 1e-5)

    def test_anamorphic(self):
        self._check("OpenOptics_Anamorphic", squeeze=1.5, mode="desqueeze")

    def test_chromatic_aberration(self):
        self._check("OpenOptics_ChromaticAberration", ca_r=0.01, ca_b=-0.01)

    def test_focal_crop(self):
        self._check("OpenOptics_FocalCrop", source_focal_mm=24, target_focal_mm=50)


if __name__ == "__main__":
    unittest.main()
