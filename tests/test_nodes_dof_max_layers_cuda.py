import re
import unittest
from unittest import mock

import torch

from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField


def _run(max_layers=None):
    """Run the node on CUDA on a seeded 32x32 scene; return (image, layers, log lines)."""
    torch.manual_seed(0)
    image = torch.rand(1, 32, 32, 3)
    ramp = torch.linspace(0.8, 20.0, 32 * 32).reshape(1, 32, 32)
    kwargs = {} if max_layers is None else {"max_layers": max_layers}
    with mock.patch.dict("os.environ", {"OPEN_OPTICS_DEVICE": "cuda"}):
        with unittest.TestCase().assertLogs("open_optics_nodes", "INFO") as cm:
            out, _coc = OpenOptics_DepthOfField().apply(
                image, focal_mm=85.0, f_number=1.8, focus_m=3.0,
                max_radius_px=16, depth_mask=ramp, **kwargs)
    messages = [r.getMessage() for r in cm.records]
    layers = [int(m.group(1)) for msg in messages
              if (m := re.search(r"layers=(\d+)", msg))]
    assert len(layers) == 1
    return out, layers[0], messages


@unittest.skipUnless(torch.cuda.is_available(), "CUDA is not available")
class TestDofMaxLayersCuda(unittest.TestCase):
    def tearDown(self):
        torch.cuda.empty_cache()

    def _check(self, max_layers):
        out, layers, messages = _run(max_layers)
        self.assertTrue(torch.isfinite(out).all())
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)
        self.assertLessEqual(layers, max_layers)
        self.assertTrue(any("device=cuda:0" in m for m in messages))

    def test_max_layers_1(self):
        self._check(1)

    def test_max_layers_2(self):
        self._check(2)

    def test_max_layers_3(self):
        self._check(3)

    def test_default_close_to_64_layers(self):
        default, _, _ = _run()
        full, _, _ = _run(64)
        self.assertLess(float((default - full).abs().mean()), 0.02)


if __name__ == "__main__":
    unittest.main()
