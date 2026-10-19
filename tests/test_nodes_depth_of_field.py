import inspect
import unittest

import torch

from open_optics import coc
from open_optics_nodes import dof_math
from open_optics_nodes.depth_of_field import _LAYERS, OpenOptics_DepthOfField


class TestDepthOfFieldValues(unittest.TestCase):
    def test_all_in_focus_returns_input(self):
        g = torch.Generator().manual_seed(1)
        img = torch.rand(1, 32, 32, 3, generator=g)
        depth = torch.full((1, 32, 32), 3.0)
        out, coc_px = OpenOptics_DepthOfField().apply(img, focus_m=3.0, depth_mask=depth)
        self.assertTrue(torch.allclose(out, img, atol=1e-5))
        self.assertTrue(bool((coc_px == 0).all()))

    def test_known_depth_coc(self):
        img = torch.rand(1, 32, 32, 3)
        depth = torch.full((1, 32, 32), 1.0)
        _, coc_px = OpenOptics_DepthOfField().apply(
            img, focal_mm=50.0, f_number=2.8, focus_m=3.0, sensor_width_mm=36.0,
            max_radius_px=16, depth_mask=depth)
        blur = coc.blur_diameter_mm(50.0, 2.8, 3000.0, 1000.0)
        expected = coc.blur_radius_px(blur, 32, 36.0, max_px=16) / 16
        self.assertGreater(expected, 0.0)
        self.assertAlmostEqual(float(coc_px[0, 0, 0]), expected, delta=1e-4)
        self.assertAlmostEqual(float(coc_px[0, 31, 31]), expected, delta=1e-4)

    def _two_plane(self):
        img = torch.zeros(1, 32, 32, 3)
        img[:, :, :16, :] = 1.0
        depth = torch.full((1, 32, 32), 100.0)
        depth[:, :, :16] = 3.0
        return img, depth

    def test_no_halo_in_focus_half(self):
        img, depth = self._two_plane()
        out, _ = OpenOptics_DepthOfField().apply(
            img, focus_m=3.0, colorspace="linear", depth_mask=depth)
        left = out[:, :, :16, :]
        self.assertLessEqual(float((left - 1.0).abs().max()), 1e-4)

    def test_depth_image_matches_mask(self):
        img, depth = self._two_plane()
        node = OpenOptics_DepthOfField()
        a, ca = node.apply(img, colorspace="linear", depth_mask=depth)
        b, cb = node.apply(img, colorspace="linear",
                           depth_image=depth.unsqueeze(-1).repeat(1, 1, 1, 3))
        self.assertTrue(torch.allclose(a, b))
        self.assertTrue(torch.allclose(ca, cb))

    def _run_constant_depth(self, depth_m, f_number):
        torch.manual_seed(7)
        img = torch.rand(1, 32, 32, 3, dtype=torch.float32)
        depth = torch.full((1, 32, 32), depth_m)
        out, coc_px = OpenOptics_DepthOfField().apply(
            img, focal_mm=200.0, f_number=f_number, focus_m=2.0, sensor_width_mm=36.0,
            max_radius_px=8, quality="draft", colorspace="linear", depth_mask=depth)
        return img, out, coc_px

    def test_depth_at_focus_returns_input(self):
        img, out, _ = self._run_constant_depth(2.0, 2.8)
        self.assertLessEqual(float((out - img).abs().max()), 1e-4)

    def test_far_depth_blurs_image(self):
        img, out, coc_px = self._run_constant_depth(20.0, 2.8)
        self.assertGreater(float((out - img).abs().mean()), 0.01)
        self.assertGreater(float(coc_px.max()), 0.0)

    def test_lower_f_number_blurs_more(self):
        img, wide, _ = self._run_constant_depth(20.0, 1.8)
        _, narrow, _ = self._run_constant_depth(20.0, 8.0)
        self.assertGreater(float((wide - img).abs().mean()),
                           float((narrow - img).abs().mean()))

    def test_two_plane_sharp_edge_picks_up_no_background_blur(self):
        img = torch.zeros(1, 32, 32, 3, dtype=torch.float32)
        img[:, :, :16, :] = 1.0
        depth = torch.full((1, 32, 32), 20.0)
        depth[:, :, :16] = 2.0
        out, coc_px = OpenOptics_DepthOfField().apply(
            img, focal_mm=50.0, f_number=2.8, focus_m=2.0, sensor_width_mm=36.0,
            max_radius_px=8, quality="draft", colorspace="linear", depth_mask=depth)
        self.assertLessEqual(float((out[:, :, :12, :] - 1.0).abs().max()), 1e-4)
        self.assertGreaterEqual(float(out[:, :, 15, :].min()), 0.9)
        self.assertGreater(float(coc_px[:, :, 16:].min()), 0.0)

    def test_depth_input_errors(self):
        img = torch.rand(1, 32, 32, 3)
        node = OpenOptics_DepthOfField()
        with self.assertRaisesRegex(ValueError, "Exactly one of depth_mask or depth_image"):
            node.apply(img)
        with self.assertRaisesRegex(ValueError, "Exactly one of depth_mask or depth_image"):
            node.apply(img, depth_mask=torch.ones(1, 32, 32),
                       depth_image=torch.ones(1, 32, 32, 3))
        with self.assertRaises(ValueError):
            node.apply(img, depth_mask=torch.ones(1, 16, 16))

    def test_depth_input_errors_name_both_inputs(self):
        img = torch.rand(1, 32, 32, 3)
        node = OpenOptics_DepthOfField()
        with self.assertRaisesRegex(ValueError, "depth_mask.*depth_image"):
            node.apply(img)
        with self.assertRaisesRegex(ValueError, "depth_mask.*depth_image"):
            node.apply(img, depth_mask=torch.ones(1, 32, 32),
                       depth_image=torch.ones(1, 32, 32, 3))

    def test_bad_values_name_their_input(self):
        img = torch.rand(1, 32, 32, 3)
        depth = torch.full((1, 32, 32), 3.0)
        node = OpenOptics_DepthOfField()
        for name in ("focal_mm", "f_number", "focus_m", "sensor_width_mm"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, name):
                    node.apply(img, depth_mask=depth, **{name: 0})
        with self.assertRaisesRegex(ValueError, "max_radius_px"):
            node.apply(img, depth_mask=depth, max_radius_px=-1)
        with self.assertRaisesRegex(ValueError, "quality"):
            node.apply(img, depth_mask=depth, quality="bogus")


class TestCocMask(unittest.TestCase):
    def test_coc_saturates_at_one(self):
        img = torch.rand(1, 32, 32, 3)
        depth = torch.full((1, 32, 32), 0.2)
        _, coc_px = OpenOptics_DepthOfField().apply(
            img, focal_mm=100.0, f_number=1.4, focus_m=3.0, sensor_width_mm=36.0,
            max_radius_px=2, depth_mask=depth)
        self.assertLessEqual(float((coc_px - 1.0).abs().max()), 1e-6)
        blur = coc.blur_diameter_mm(100, 1.4, 3000, 200)
        self.assertGreater(coc.blur_radius_px(blur, 32, 36.0, max_px=1000) / 2, 1)

    def test_coc_per_pixel_map(self):
        img = torch.rand(1, 32, 32, 3)
        depth = torch.full((1, 32, 32), 3.0)
        depth[:, :, 16:] = 1.0
        _, coc_px = OpenOptics_DepthOfField().apply(
            img, focal_mm=50.0, f_number=2.8, focus_m=3.0, sensor_width_mm=36.0,
            max_radius_px=16, depth_mask=depth)
        self.assertEqual(tuple(coc_px.shape), (1, 32, 32))
        self.assertEqual(coc_px.dtype, torch.float32)
        self.assertTrue(bool((coc_px[:, :, :16] == 0).all()))
        blur = coc.blur_diameter_mm(50, 2.8, 3000, 1000)
        expected = coc.blur_radius_px(blur, 32, 36.0, max_px=16) / 16
        self.assertLessEqual(float((coc_px[:, :, 16:] - expected).abs().max()), 1e-4)
        self.assertGreaterEqual(float(coc_px.min()), 0.0)
        self.assertLessEqual(float(coc_px.max()), 1.0)


class TestDepthOfFieldEdgeCases(unittest.TestCase):
    def _img(self):
        g = torch.Generator().manual_seed(3)
        return torch.rand(1, 16, 16, 3, generator=g)

    def test_nan_and_zero_depth_finite(self):
        img = self._img()
        depth = torch.full((1, 16, 16), 3.0)
        depth[0, 0, 0] = float("nan")
        depth[0, 0, 1] = 0.0
        depth[0, 0, 2] = float("inf")
        depth[0, 0, 3] = -1.0
        for quality in ("draft", "normal"):
            with self.subTest(quality=quality):
                out, coc_px = OpenOptics_DepthOfField().apply(
                    img, max_radius_px=4, quality=quality, depth_mask=depth)
                self.assertTrue(bool(torch.isfinite(out).all()))
                self.assertGreaterEqual(float(out.min()), 0.0)
                self.assertLessEqual(float(out.max()), 1.0)
                self.assertTrue(bool(torch.isfinite(coc_px).all()))
                self.assertGreaterEqual(float(coc_px.min()), 0.0)
                self.assertLessEqual(float(coc_px.max()), 1.0)

    def test_max_layers_input_definition(self):
        optional = OpenOptics_DepthOfField.INPUT_TYPES()["optional"]
        self.assertEqual(optional["max_layers"],
                         ("INT", {"default": 12, "min": 1, "max": 64, "step": 1}))
        self.assertEqual(list(optional)[-1], "max_layers")
        img = self._img()
        depth = torch.full((1, 16, 16), 3.0)
        for bad in (0, 65, True, 2.5):
            with self.subTest(max_layers=bad):
                with self.assertRaisesRegex(ValueError, "max_layers"):
                    OpenOptics_DepthOfField().apply(img, depth_mask=depth, max_layers=bad)

    def test_max_radius_zero_identity(self):
        img = self._img()
        depth = torch.full((1, 16, 16), 20.0)
        out, coc_px = OpenOptics_DepthOfField().apply(
            img, max_radius_px=0, depth_mask=depth)
        self.assertTrue(torch.allclose(out, img, atol=1e-6))
        self.assertEqual(tuple(coc_px.shape), (1, 16, 16))
        self.assertTrue(bool((coc_px == 0).all()))

    def test_small_radius_nearly_unblurred(self):
        img = self._img()
        depth = torch.full((1, 16, 16), 50.0)
        out, _ = OpenOptics_DepthOfField().apply(
            img, max_radius_px=1, depth_mask=depth)
        self.assertLess(float((out - img).abs().mean()), 0.2)

    def test_uniform_depth_runs(self):
        img = self._img()
        depth = torch.full((1, 16, 16), 5.0)
        out, coc_px = OpenOptics_DepthOfField().apply(
            img, max_radius_px=4, depth_mask=depth)
        self.assertEqual(tuple(out.shape), (1, 16, 16, 3))
        self.assertEqual(tuple(coc_px.shape), (1, 16, 16))

    def test_invalid_quality_raises(self):
        with self.assertRaisesRegex(ValueError, "quality"):
            OpenOptics_DepthOfField().apply(
                self._img(), quality="ultra", depth_mask=torch.full((1, 16, 16), 3.0))


class TestDepthOfFieldLayers(unittest.TestCase):
    def _split(self, left_depth, right_depth):
        img = torch.zeros(1, 32, 32, 3)
        img[:, :, :16, :] = 1.0
        depth = torch.full((1, 32, 32), right_depth)
        depth[:, :, :16] = left_depth
        return img, depth

    def test_normal_and_draft_no_halo(self):
        img, depth = self._split(2.0, 30.0)
        for quality in ("draft", "normal"):
            out, _ = OpenOptics_DepthOfField().apply(
                img, focal_mm=50.0, f_number=2.8, focus_m=2.0, max_radius_px=8,
                quality=quality, colorspace="linear", depth_mask=depth)
            left = out[:, :, :14, :]
            self.assertLessEqual(float((left - 1.0).abs().max()), 1e-4, quality)
            self.assertGreaterEqual(float(out[:, :, 15, :].min()), 0.9, quality)

    def test_blurred_foreground_spreads_over_background(self):
        img, depth = self._split(0.7, 3.0)
        out, _ = OpenOptics_DepthOfField().apply(
            img, focal_mm=85.0, f_number=1.8, focus_m=3.0, max_radius_px=8,
            colorspace="linear", depth_mask=depth)
        self.assertGreater(float(out[:, :, 17, :].mean()), 0.01)
        self.assertLess(float(out[:, :, 28:32, :].max()), 1e-3)

    def test_sharp_subject_inside_wide_depth_range_stays_sharp(self):
        # Regression: layers were equal bins in metres with each bin's mean CoC,
        # so a subject at focus shared a bin with blurred ground and lost its
        # sharpness. Subject at 1.15 m (focus), ground at 4 m and a far strip at
        # 40 m: equal metre bins put 1.15 m and 4 m together.
        # 85 mm f/1.4 at 1.15 m: f^2/(N(s-f)) = 7225/(1.4*1065) = 4.846 mm;
        # at 4 m the diameter is 4.846*(4-1.15)/4 = 3.453 mm = 6.14 px on a
        # 64 px, 36 mm frame, a radius of 3.07 px.
        gen = torch.Generator().manual_seed(3)
        img = torch.rand(1, 64, 64, 3, generator=gen)
        depth = torch.full((1, 64, 64), 4.0)
        depth[:, :, :24] = 1.15
        depth[:, :8, 24:] = 40.0
        for quality in ("draft", "normal"):
            out, coc_px = OpenOptics_DepthOfField().apply(
                img, focal_mm=85.0, f_number=1.4, focus_m=1.15, sensor_width_mm=36.0,
                max_radius_px=16, quality=quality, colorspace="linear", depth_mask=depth)
            self.assertAlmostEqual(float(coc_px[0, 32, 40]) * 16, 3.07, delta=0.01)
            subject = (out[:, :, :24] - img[:, :, :24]).abs().max()
            self.assertLessEqual(float(subject), 1e-4, quality)
            ground_in = img[:, 16:56, 32:56]
            ground_out = out[:, 16:56, 32:56]
            ratio = float(ground_out.diff(dim=2).var() / ground_in.diff(dim=2).var())
            self.assertLess(ratio, 0.25, quality)

    def test_normal_at_least_as_close_to_fine_reference(self):
        gen = torch.Generator().manual_seed(0)
        img = torch.rand(1, 32, 32, 3, generator=gen)
        ramp = torch.linspace(1.0, 20.0, 32)
        depth = ramp.view(1, 1, 32).expand(1, 32, 32).contiguous()
        args = dict(focal_mm=85.0, f_number=1.8, focus_m=3.0, max_radius_px=8)
        radius = dof_math.coc_radius_map(
            dof_math.sanitize_depth(depth), 85.0, 1.8, 3.0, 36.0, 8)
        ref = dof_math.composite_layers(
            img, dof_math.sanitize_depth(depth), radius, 32, 3.0)
        errs = {}
        for quality in ("draft", "normal"):
            out, _ = OpenOptics_DepthOfField().apply(
                img, quality=quality, colorspace="linear", depth_mask=depth, **args)
            errs[quality] = float((out - ref).abs().mean())
        self.assertLessEqual(errs["normal"], errs["draft"] + 1e-6)
        self.assertGreater(_LAYERS["normal"], _LAYERS["draft"])


class TestDepthOfFieldChunking(unittest.TestCase):
    def test_input_types(self):
        spec = OpenOptics_DepthOfField.INPUT_TYPES()["optional"]["chunk_frames"]
        self.assertEqual(spec[0], "INT")
        self.assertEqual(spec[1]["default"], 8)
        self.assertEqual(spec[1]["min"], 1)

    def test_chunk_frames_is_optional_with_default(self):
        types = OpenOptics_DepthOfField.INPUT_TYPES()
        self.assertNotIn("chunk_frames", types["required"])
        self.assertEqual(types["optional"]["chunk_frames"][1]["default"], 8)
        params = inspect.signature(OpenOptics_DepthOfField.apply).parameters
        self.assertEqual(params["chunk_frames"].default, 8)
        self.assertEqual(params["max_layers"].default, 12)

    def test_zero_raises(self):
        img = torch.rand(1, 32, 32, 3)
        with self.assertRaises(ValueError):
            OpenOptics_DepthOfField().apply(
                img, depth_mask=torch.ones(1, 32, 32), chunk_frames=0)

    def test_chunks_match_all_frames(self):
        g = torch.Generator().manual_seed(7)
        img = torch.rand(4, 32, 32, 3, generator=g)
        depth = 1.0 + 9.0 * torch.rand(4, 32, 32, generator=g)
        before = img.clone()
        node = OpenOptics_DepthOfField()
        ref, ref_coc = node.apply(img, depth_mask=depth, chunk_frames=4)
        for n in (1, 3):
            out, coc_px = node.apply(img, depth_mask=depth, chunk_frames=n)
            self.assertEqual(out.shape, ref.shape)
            self.assertEqual(coc_px.shape, ref_coc.shape)
            self.assertTrue(torch.allclose(out, ref, atol=1e-5))
            self.assertTrue(torch.allclose(coc_px, ref_coc, atol=1e-5))
        self.assertTrue(torch.equal(img, before))

    def test_outputs_are_cpu_float32(self):
        g = torch.Generator().manual_seed(11)
        img = torch.rand(4, 32, 32, 3, generator=g)
        depth = 1.0 + 9.0 * torch.rand(4, 32, 32, generator=g)
        before = img.clone()
        out, coc_px = OpenOptics_DepthOfField().apply(img, depth_mask=depth, chunk_frames=3)
        for t in (out, coc_px):
            self.assertEqual(t.device.type, "cpu")
            self.assertEqual(t.dtype, torch.float32)
        self.assertTrue(torch.equal(img, before))


if __name__ == "__main__":
    unittest.main()
