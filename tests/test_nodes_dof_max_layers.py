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


if __name__ == "__main__":
    unittest.main()
