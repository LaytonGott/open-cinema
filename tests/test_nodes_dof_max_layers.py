import re
import unittest
from unittest import mock

import torch

from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField


def _run(max_layers):
    """Run the node on a seeded 32x32 scene; return (image, layers from the log)."""
    torch.manual_seed(0)
    image = torch.rand(1, 32, 32, 3)
    ramp = torch.linspace(0.8, 20.0, 32 * 32).reshape(1, 32, 32)
    with mock.patch.dict("os.environ", {"OPEN_OPTICS_DEVICE": "cpu"}):
        with unittest.TestCase().assertLogs("open_optics_nodes", "INFO") as cm:
            out, _coc = OpenOptics_DepthOfField().apply(
                image, focal_mm=85.0, f_number=1.8, focus_m=3.0,
                max_radius_px=16, depth_mask=ramp, max_layers=max_layers)
    layers = [int(m.group(1)) for r in cm.records
              if (m := re.search(r"layers=(\d+)", r.getMessage()))]
    assert len(layers) == 1
    return out, layers[0]


class TestDofMaxLayers(unittest.TestCase):
    def _check(self, max_layers):
        out, layers = _run(max_layers)
        self.assertTrue(torch.isfinite(out).all())
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)
        self.assertLessEqual(layers, max_layers)
        return layers

    def test_max_layers_1(self):
        self._check(1)

    def test_max_layers_2(self):
        self._check(2)

    def test_max_layers_3(self):
        self._check(3)

    def test_larger_cap_reports_at_least_as_many_layers(self):
        small = self._check(3)
        large = self._check(64)
        self.assertGreaterEqual(large, small)

    def test_many_distinct_depths_stay_within_default_cap(self):
        torch.manual_seed(0)
        image = torch.rand(2, 48, 64, 3)
        ramp = torch.linspace(0.6, 9.0, 48 * 64).reshape(1, 48, 64).repeat(2, 1, 1)
        with mock.patch.dict("os.environ", {"OPEN_OPTICS_DEVICE": "cpu"}):
            with self.assertLogs("open_optics_nodes", "INFO") as cm:
                out, coc = OpenOptics_DepthOfField().apply(
                    image, focal_mm=50.0, f_number=1.8, focus_m=2.0,
                    max_radius_px=24, depth_mask=ramp, sensor_width_mm=10.0)
        layers = [int(m.group(1)) for r in cm.records
                  if (m := re.search(r"layers=(\d+)", r.getMessage()))]
        self.assertEqual(len(layers), 1)
        self.assertLessEqual(layers[0], 12)
        self.assertTrue(torch.isfinite(out).all())
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)
        change = (out - image).abs().mean(dim=-1)
        px = coc * 24
        sharp, blurry = px < 0.2, px > 4.0
        self.assertTrue(bool(sharp.any()))
        self.assertTrue(bool(blurry.any()))
        self.assertLess(float(change[sharp].mean()), 0.01)
        self.assertGreater(float(change[blurry].mean()), 0.02)


if __name__ == "__main__":
    unittest.main()
