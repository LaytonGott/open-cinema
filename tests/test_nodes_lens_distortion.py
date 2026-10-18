import unittest

import torch

import open_optics_nodes
from open_optics_nodes.lens_distortion import OpenOptics_LensDistortion


def _image():
    gen = torch.Generator().manual_seed(0)
    return torch.rand(1, 8, 8, 3, generator=gen, dtype=torch.float32)


class TestLensDistortionNode(unittest.TestCase):
    def test_defaults_are_identity(self):
        img = _image()
        (out,) = OpenOptics_LensDistortion().apply(img)
        self.assertTrue(torch.allclose(out, img, atol=1e-5))

    def test_crop_with_zero_coefficients_is_identity(self):
        img = _image()
        (out,) = OpenOptics_LensDistortion().apply(img, fit="crop")
        self.assertTrue(torch.allclose(out, img, atol=1e-5))
        (out,) = OpenOptics_LensDistortion().apply(img, direction="remove", fit="crop")
        self.assertTrue(torch.allclose(out, img, atol=1e-5))

    def test_remove_with_crop_is_finite_and_in_range(self):
        img = _image()
        (out,) = OpenOptics_LensDistortion().apply(
            img, k1=-0.2, direction="remove", fit="crop")
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(out.shape, img.shape)
        self.assertTrue(bool(torch.isfinite(out).all()))
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)

    def test_registration(self):
        self.assertIs(open_optics_nodes.NODE_CLASS_MAPPINGS["OpenOptics_LensDistortion"],
                      OpenOptics_LensDistortion)
        self.assertEqual(
            open_optics_nodes.NODE_DISPLAY_NAME_MAPPINGS["OpenOptics_LensDistortion"],
            "Open Optics: Lens Distortion")


if __name__ == "__main__":
    unittest.main()
