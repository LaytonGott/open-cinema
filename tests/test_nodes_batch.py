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


class DepthBatchMismatchTest(unittest.TestCase):
    def test_depth_batch_mismatch_raises(self):
        img = torch.rand(3, 16, 20, 3)
        node = OpenOptics_DepthOfField()
        for batch in (1, 2):
            with self.subTest(depth_batch=batch):
                with self.assertRaises(ValueError) as ctx:
                    node.apply(img, depth_mask=torch.ones(batch, 16, 20) * 3)
                self.assertIn("batch", str(ctx.exception))


class DepthToMetricBatchTest(unittest.TestCase):
    def test_depth_to_metric_fits_whole_batch(self):
        from open_optics_nodes.depth_to_metric import OpenOptics_DepthToMetric

        depth = torch.tensor([[[0.0, 0.5]], [[0.5, 1.0]]])
        node = OpenOptics_DepthToMetric()
        kwargs = dict(near_m=1.0, far_m=5.0, inverse_depth=False,
                      low_percentile=0.0, high_percentile=100.0)
        batch = node.convert(depth_mask=depth, **kwargs)[0]
        expected = torch.tensor([[[1.0, 3.0]], [[3.0, 5.0]]])
        self.assertTrue(torch.allclose(batch, expected, atol=1e-5))
        single = node.convert(depth_mask=depth[0:1], **kwargs)[0]
        self.assertTrue(torch.allclose(single, torch.tensor([[[1.0, 5.0]]]), atol=1e-5))
        self.assertFalse(torch.allclose(single, batch[0:1], atol=1e-5))


if __name__ == "__main__":
    unittest.main()
