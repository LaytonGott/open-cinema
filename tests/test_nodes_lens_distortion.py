import unittest

import torch

import open_optics_nodes
from open_optics import distortion, pixels
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


N = 33


def _gradient():
    u = torch.linspace(0.0, 1.0, N).reshape(1, 1, N, 1).expand(1, N, N, 1)
    v = torch.linspace(0.0, 1.0, N).reshape(1, N, 1, 1).expand(1, N, N, 1)
    return torch.cat([u, v, 0.5 * (u + v)], dim=3).contiguous()


class TestLensDistortionAgainstLibrary(unittest.TestCase):
    def test_zero_coefficients_identity_33(self):
        img = torch.rand(1, N, N, 3, generator=torch.Generator().manual_seed(1))
        (out,) = OpenOptics_LensDistortion().apply(img)
        self.assertTrue(torch.allclose(out, img, atol=1e-6))

    def test_bright_pixel_lands_where_distort_point_says(self):
        px, py = 26, 22
        img = torch.zeros(1, N, N, 3)
        img[0, py, px, :] = 1.0
        (out,) = OpenOptics_LensDistortion().apply(img, k1=-0.1, direction="apply")
        x, y = pixels.pixel_to_lens(px, py, N, N, 36.0, 35.0)
        x, y = distortion.distort_point(x, y, k1=-0.1)
        ex, ey = pixels.lens_to_pixel(x, y, N, N, 36.0, 35.0)
        gy, gx = divmod(int(out[0].sum(dim=2).argmax()), N)
        self.assertLessEqual(abs(gx - ex), 1.0)
        self.assertLessEqual(abs(gy - ey), 1.0)

    def test_apply_then_remove_round_trip(self):
        img = _gradient()
        node = OpenOptics_LensDistortion()
        (mid,) = node.apply(img, k1=-0.1, direction="apply")
        (back,) = node.apply(mid, k1=-0.1, direction="remove")
        diff = (back - img)[:, 4:N - 4, 4:N - 4, :].abs().max()
        self.assertLess(float(diff), 0.02)

    def test_crop_keeps_shape_and_range(self):
        (out,) = OpenOptics_LensDistortion().apply(
            _gradient(), k1=-0.1, direction="remove", fit="crop")
        self.assertEqual(tuple(out.shape), (1, N, N, 3))
        self.assertTrue(bool(torch.isfinite(out).all()))
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)


if __name__ == "__main__":
    unittest.main()
