"""Batch processing equals per-frame processing for the image nodes."""

import unittest

import torch

from open_optics_nodes.anamorphic import OpenOptics_Anamorphic
from open_optics_nodes.chromatic_aberration import OpenOptics_ChromaticAberration
from open_optics_nodes.focal_crop import OpenOptics_FocalCrop
from open_optics_nodes.lens_distortion import OpenOptics_LensDistortion
from open_optics_nodes.vignette import OpenOptics_Vignette


class BatchEqualsPerFrameTest(unittest.TestCase):
    def test_batch_matches_single_frames(self):
        torch.manual_seed(1234)
        image = torch.rand(3, 16, 20, 3, dtype=torch.float32)
        cases = [
            (OpenOptics_FocalCrop, {}),
            (OpenOptics_Vignette, {}),
            (OpenOptics_ChromaticAberration, {"ca_r": 0.03, "ca_b": -0.03}),
            (OpenOptics_Anamorphic, {}),
            (OpenOptics_LensDistortion, {"k1": 0.1}),
        ]
        for cls, kwargs in cases:
            with self.subTest(node=cls.__name__):
                fn = getattr(cls(), cls.FUNCTION)
                batch_out = fn(image, **kwargs)[0]
                self.assertEqual(batch_out.shape[0], 3)
                for i in range(3):
                    single_out = fn(image[i:i + 1], **kwargs)[0]
                    self.assertEqual(single_out.shape[0], 1)
                    self.assertTrue(
                        torch.allclose(batch_out[i:i + 1], single_out, atol=1e-6),
                        f"frame {i} differs",
                    )


if __name__ == "__main__":
    unittest.main()
