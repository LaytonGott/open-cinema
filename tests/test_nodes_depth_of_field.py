import unittest

import torch

from open_optics import coc
from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField


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
        for name in ("focal_mm", "f_number", "focus_m", "sensor_width_mm", "max_radius_px"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, name):
                    node.apply(img, depth_mask=depth, **{name: 0})
        with self.assertRaisesRegex(ValueError, "quality"):
            node.apply(img, depth_mask=depth, quality="bogus")


if __name__ == "__main__":
    unittest.main()
