import inspect
import unittest

import torch

import open_optics_nodes
from open_optics import distortion, pixels
from open_optics_nodes import distortion_grid
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

    def test_bad_focal_names_input(self):
        with self.assertRaises(ValueError) as ctx:
            OpenOptics_LensDistortion().apply(_image(), focal_mm=0)
        self.assertIn("focal_mm", str(ctx.exception))

    def test_bad_direction_names_input(self):
        with self.assertRaises(ValueError) as ctx:
            OpenOptics_LensDistortion().apply(_image(), direction="bogus")
        self.assertIn("direction", str(ctx.exception))

    def test_chunk_frames_input(self):
        spec = OpenOptics_LensDistortion.INPUT_TYPES()["optional"]["chunk_frames"]
        self.assertEqual(spec[0], "INT")
        self.assertEqual(spec[1]["default"], 8)
        self.assertEqual(spec[1]["min"], 1)

    def test_chunk_frames_is_optional_with_default(self):
        types = OpenOptics_LensDistortion.INPUT_TYPES()
        self.assertNotIn("chunk_frames", types["required"])
        self.assertIn("chunk_frames", types["optional"])
        self.assertEqual(types["optional"]["chunk_frames"][1]["default"], 8)
        param = inspect.signature(OpenOptics_LensDistortion.apply).parameters["chunk_frames"]
        self.assertEqual(param.default, 8)

    def test_chunk_frames_zero_raises(self):
        with self.assertRaises(ValueError) as ctx:
            OpenOptics_LensDistortion().apply(_image(), chunk_frames=0)
        self.assertIn("chunk_frames", str(ctx.exception))

    def test_chunk_sizes_match_full_and_output_on_cpu(self):
        img = torch.rand(5, 8, 8, 3, generator=torch.Generator().manual_seed(5))
        before = img.clone()
        node = OpenOptics_LensDistortion()
        (full,) = node.apply(img, k1=0.2, p1=0.01)
        for size in (1, 3):
            (out,) = node.apply(img, k1=0.2, p1=0.01, chunk_frames=size)
            self.assertEqual(out.device.type, "cpu")
            self.assertEqual(out.dtype, torch.float32)
            self.assertLess(float((out - full).abs().max()), 1e-5)
        self.assertTrue(torch.equal(img, before))

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


class TestLensDistortionPointPosition(unittest.TestCase):
    def _centroid(self, px, py, **kw):
        size = 64
        img = torch.zeros(1, size, size, 3)
        img[0, py, px, :] = 1.0
        (out,) = OpenOptics_LensDistortion().apply(
            img, focal_mm=35, sensor_width_mm=36, direction="apply", **kw)
        ch = out[0, :, :, 0]
        idx = torch.arange(size, dtype=torch.float32)
        total = ch.sum()
        cx = float((ch.sum(dim=0) * idx).sum() / total)
        cy = float((ch.sum(dim=1) * idx).sum() / total)
        x, y = pixels.pixel_to_lens(px, py, size, size, 36.0, 35.0)
        x, y = distortion.distort_point(x, y, **kw)
        ex, ey = pixels.lens_to_pixel(x, y, size, size, 36.0, 35.0)
        return (cx, cy), (ex, ey)

    def test_barrel_k1_centroid(self):
        (cx, cy), (ex, ey) = self._centroid(45, 20, k1=-0.1)
        self.assertAlmostEqual(cx, ex, delta=0.5)
        self.assertAlmostEqual(cy, ey, delta=0.5)

    def test_k1_and_p1_centroid(self):
        (cx, cy), (ex, ey) = self._centroid(18, 40, k1=0.1, p1=0.01)
        self.assertAlmostEqual(cx, ex, delta=0.5)
        self.assertAlmostEqual(cy, ey, delta=0.5)

    def test_zero_coefficients_remove_is_identity(self):
        img = torch.rand(1, 64, 64, 3, generator=torch.Generator().manual_seed(3))
        (out,) = OpenOptics_LensDistortion().apply(
            img, k1=0, k2=0, k3=0, p1=0, p2=0, direction="remove")
        self.assertTrue(torch.allclose(out, img, atol=1e-5))


def _smooth_image():
    size = 64
    u = torch.linspace(0.0, 1.0, size).reshape(1, 1, size).expand(1, size, size)
    v = torch.linspace(0.0, 1.0, size).reshape(1, size, 1).expand(1, size, size)
    c2 = 0.5 * (u + v) + 0.1 * torch.sin(2.0 * torch.pi * u) * torch.sin(2.0 * torch.pi * v)
    return torch.stack([u, v, c2.clamp(0.0, 1.0)], dim=3).contiguous()


class TestLensDistortionRoundTrip(unittest.TestCase):
    # Tolerance 0.03 on the central region [8:56, 8:56] (8-pixel border excluded).
    TOL = 0.03

    def _check(self, first, second, **kw):
        img = _smooth_image()
        node = OpenOptics_LensDistortion()
        (mid,) = node.apply(img, direction=first, fit="keep", **kw)
        (back,) = node.apply(mid, direction=second, fit="keep", **kw)
        diff = (back - img)[:, 8:56, 8:56, :].abs().max()
        self.assertLess(float(diff), self.TOL)

    def test_positive_k1(self):
        self._check("apply", "remove", k1=0.1)

    def test_negative_k1(self):
        self._check("apply", "remove", k1=-0.1)

    def test_tangential(self):
        self._check("apply", "remove", k1=0.0, p1=0.01, p2=-0.01)

    def test_remove_then_apply_negative_k1(self):
        self._check("remove", "apply", k1=-0.1)


class TestLensDistortionFitModes(unittest.TestCase):
    def test_keep_fills_outside_with_black(self):
        corner = distortion_grid.build_source_grid(
            33, 33, 35, 36, 0.3, 0, 0, 0, 0, "remove")[0][0]
        self.assertLess(corner[0], 0)
        self.assertLess(corner[1], 0)
        img = torch.ones(1, 33, 33, 3, dtype=torch.float32)
        (out,) = OpenOptics_LensDistortion().apply(
            img, focal_mm=35.0, sensor_width_mm=36.0, k1=0.3,
            direction="remove", fit="keep")
        for c in range(3):
            self.assertEqual(float(out[0, 0, 0, c]), 0.0)
            self.assertAlmostEqual(float(out[0, 16, 16, c]), 1.0, delta=1e-5)


class TestLensDistortionCropFit(unittest.TestCase):
    def _check(self, direction, k1, check_keep=True):
        img = torch.ones(1, 33, 33, 3, dtype=torch.float32)
        node = OpenOptics_LensDistortion()
        kw = dict(focal_mm=35.0, sensor_width_mm=36.0, k1=k1,
                  direction=direction)
        (crop,) = node.apply(img, fit="crop", **kw)
        self.assertEqual(crop.shape, img.shape)
        self.assertGreater(float(crop.min()), 0.999)
        if check_keep:
            (keep,) = node.apply(img, fit="keep", **kw)
            self.assertEqual(float(keep.min()), 0.0)

    def test_remove_k1_positive(self):
        self._check("remove", 0.3)

    def test_apply_k1_negative(self):
        self._check("apply", -0.3, check_keep=False)


if __name__ == "__main__":
    unittest.main()
