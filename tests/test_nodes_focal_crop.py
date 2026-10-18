import math
import unittest

import torch

from open_optics import fov
from open_optics_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from open_optics_nodes.focal_crop import OpenOptics_FocalCrop


def _image():
    g = torch.Generator().manual_seed(0)
    return torch.rand(1, 32, 32, 3, generator=g)


class FocalCropTest(unittest.TestCase):
    def test_cropped_is_centre_half(self):
        img = _image()
        (out,) = OpenOptics_FocalCrop().crop(img, 25.0, 50.0, "cropped")
        self.assertEqual(tuple(out.shape), (1, 16, 16, 3))
        self.assertTrue(torch.equal(out, img[:, 8:24, 8:24]))

    def test_original_size(self):
        (out,) = OpenOptics_FocalCrop().crop(_image(), 25.0, 50.0, "original")
        self.assertEqual(tuple(out.shape), (1, 32, 32, 3))
        self.assertEqual(out.dtype, torch.float32)

    def test_double_zoom_on_64_image(self):
        torch.manual_seed(0)
        img = torch.rand(1, 64, 64, 3)
        (out,) = OpenOptics_FocalCrop().crop(img, 24.0, 48.0, "cropped")
        self.assertEqual(tuple(out.shape), (1, 32, 32, 3))
        self.assertTrue(torch.equal(out, img[:, 16:48, 16:48, :]))
        (out,) = OpenOptics_FocalCrop().crop(img, 24.0, 48.0, "original")
        self.assertEqual(tuple(out.shape), (1, 64, 64, 3))

    def test_crop_size_matches_angle_of_view(self):
        img = torch.rand(1, 60, 60, 3)
        (out,) = OpenOptics_FocalCrop().crop(img, 24.0, 36.0, "cropped")
        self.assertEqual(out.shape[1], 40)
        self.assertEqual(out.shape[2], 40)
        half_target = math.radians(fov.angle_of_view(36.0, 36.0)) / 2
        half_source = math.radians(fov.angle_of_view(24.0, 36.0)) / 2
        expected = math.tan(half_target) / math.tan(half_source) * 60
        self.assertAlmostEqual(out.shape[1], expected, delta=0.5)

    def test_equal_focals_identity(self):
        img = _image()
        for mode in ("original", "cropped"):
            (out,) = OpenOptics_FocalCrop().crop(img, 35.0, 35.0, mode)
            self.assertTrue(torch.equal(out, img))

    def test_target_below_source_raises(self):
        with self.assertRaisesRegex(ValueError, "target_focal_mm"):
            OpenOptics_FocalCrop().crop(_image(), 50.0, 24.0, "original")

    def test_nonpositive_raises(self):
        with self.assertRaisesRegex(ValueError, "source_focal_mm"):
            OpenOptics_FocalCrop().crop(_image(), 0.0, 50.0, "original")
        with self.assertRaisesRegex(ValueError, "target_focal_mm"):
            OpenOptics_FocalCrop().crop(_image(), 24.0, 0.0, "original")

    def test_bad_output_size_raises(self):
        with self.assertRaisesRegex(ValueError, "output_size"):
            OpenOptics_FocalCrop().crop(_image(), 24.0, 50.0, "bogus")

    def test_batch_matches_single_frames(self):
        img = torch.rand(2, 33, 31, 3, generator=torch.Generator().manual_seed(1))
        for mode in ("original", "cropped"):
            (out,) = OpenOptics_FocalCrop().crop(img, 24.0, 48.0, mode)
            self.assertEqual(out.shape[0], 2)
            for i in range(2):
                (single,) = OpenOptics_FocalCrop().crop(img[i:i + 1], 24.0, 48.0, mode)
                self.assertTrue(torch.allclose(out[i:i + 1], single, atol=1e-6))

    def test_extreme_ratio_never_empty(self):
        img = torch.rand(1, 64, 64, 3, generator=torch.Generator().manual_seed(2))
        expected = {"cropped": (1, 1, 1, 3), "original": (1, 64, 64, 3)}
        for mode, shape in expected.items():
            (out,) = OpenOptics_FocalCrop().crop(img, 1.0, 1000.0, mode)
            self.assertEqual(tuple(out.shape), shape)
            self.assertEqual(out.dtype, torch.float32)
            self.assertTrue(torch.isfinite(out).all())

    def test_odd_size_keeps_at_least_one_pixel(self):
        img = torch.rand(1, 5, 7, 3, generator=torch.Generator().manual_seed(3))
        (out,) = OpenOptics_FocalCrop().crop(img, 24.0, 50.0, "cropped")
        self.assertTrue(1 <= out.shape[1] <= 5)
        self.assertTrue(1 <= out.shape[2] <= 7)

    def test_registered(self):
        self.assertIs(NODE_CLASS_MAPPINGS["OpenOptics_FocalCrop"], OpenOptics_FocalCrop)
        self.assertEqual(NODE_DISPLAY_NAME_MAPPINGS["OpenOptics_FocalCrop"], "Open Optics: Focal Crop")


if __name__ == "__main__":
    unittest.main()
