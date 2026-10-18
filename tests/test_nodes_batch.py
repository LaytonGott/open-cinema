"""Batch processing equals per-frame processing for the image nodes."""

import unittest

import torch

from open_optics_nodes.anamorphic import OpenOptics_Anamorphic
from open_optics_nodes.chromatic_aberration import OpenOptics_ChromaticAberration
from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField
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


class DepthOfFieldBatchTest(unittest.TestCase):
    def test_dof_batch_matches_per_frame(self):
        torch.manual_seed(0)
        img = torch.rand(3, 16, 20, 3)
        depth = torch.rand(3, 16, 20) * 4 + 1
        node = OpenOptics_DepthOfField()
        out, coc = node.apply(img, quality="draft", max_radius_px=4, depth_mask=depth)
        self.assertEqual(out.shape[0], 3)
        self.assertEqual(coc.shape[0], 3)
        for i in range(3):
            single_out, single_coc = node.apply(
                img[i:i + 1], quality="draft", max_radius_px=4,
                depth_mask=depth[i:i + 1],
            )
            self.assertTrue(torch.allclose(out[i], single_out[0], atol=1e-5))
            self.assertTrue(torch.allclose(coc[i], single_coc[0], atol=1e-5))


if __name__ == "__main__":
    unittest.main()
