import unittest

import torch

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

    def test_registered(self):
        self.assertIs(NODE_CLASS_MAPPINGS["OpenOptics_FocalCrop"], OpenOptics_FocalCrop)
        self.assertEqual(NODE_DISPLAY_NAME_MAPPINGS["OpenOptics_FocalCrop"], "Open Optics: Focal Crop")


if __name__ == "__main__":
    unittest.main()
