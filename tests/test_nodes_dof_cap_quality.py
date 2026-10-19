"""Depth of Field: the default layer cap stays close to 64 layers, and blur grows with CoC."""
import os
import unittest
from unittest import mock

import torch

from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField

SIZE = 48
BORDER = 16


def _scene():
    g = torch.Generator().manual_seed(5)
    low = torch.rand(1, 6, 6, 3, generator=g)
    img = torch.nn.functional.interpolate(
        low.permute(0, 3, 1, 2), size=(SIZE, SIZE), mode="bilinear",
        align_corners=False).permute(0, 2, 3, 1).contiguous()
    img[:, :, SIZE // 2:, :] = 1.0 - img[:, :, SIZE // 2:, :]  # a hard vertical edge
    ramp = torch.linspace(0.8, 20.0, SIZE)
    depth = ramp.view(1, SIZE, 1).expand(1, SIZE, SIZE).contiguous()
    return img.clamp(0, 1), depth


class TestDofCapQuality(unittest.TestCase):
    def _run(self, **extra):
        img, depth = _scene()
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cpu"}):
            out, coc_px = OpenOptics_DepthOfField().apply(
                img, focal_mm=85.0, f_number=1.8, focus_m=3.0, max_radius_px=16,
                depth_mask=depth, **extra)
        return img, depth, out, coc_px

    def test_default_cap_close_to_64_layers(self):
        _, _, default, _ = self._run()
        _, _, full, _ = self._run(max_layers=64)
        self.assertLess(float((default - full).abs().mean()), 0.02)

    def test_max_layers_64_finite_and_in_range(self):
        _, _, full, _ = self._run(max_layers=64)
        self.assertTrue(bool(torch.isfinite(full).all()))
        self.assertGreaterEqual(float(full.min()), 0.0)
        self.assertLessEqual(float(full.max()), 1.0)

    def test_blur_rises_with_coc(self):
        img, depth, out, coc_px = self._run()
        change = (out - img).abs().mean(dim=-1)[0]
        coc_rows = coc_px[0, :, SIZE // 2]
        rows = torch.arange(SIZE)
        # The border is excluded in columns; rows are kept because the whole
        # ramp is sub-pixel blur beyond the focus plane for these lens settings.
        r = rows[coc_rows > 0]
        c = coc_rows[r]
        self.assertGreater(float(c.max()), float(c.min()))
        order = torch.argsort(c)
        bands = torch.tensor_split(r[order], 3)
        means = []
        for band in bands:
            means.append(float(change[band, BORDER:SIZE - BORDER].mean()))
        self.assertEqual(len(means), 3)
        # Below about one pixel of radius the node leaves pixels untouched, so
        # the low bands may tie at zero (up to float noise); the top band must blur.
        self.assertLessEqual(means[0], means[1] + 1e-6)
        self.assertLessEqual(means[1], means[2] + 1e-6)
        self.assertGreater(means[2], means[0] + 1e-3)


if __name__ == "__main__":
    unittest.main()
