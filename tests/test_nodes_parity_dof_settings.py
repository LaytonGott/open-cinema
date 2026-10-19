import os
import unittest

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS


class TestDepthOfFieldSettingsParity(unittest.TestCase):
    def setUp(self):
        self._old_device = os.environ.get("OPEN_OPTICS_DEVICE")
        torch.manual_seed(0)
        self.image = torch.rand(3, 32, 32, 3, dtype=torch.float32)
        col = torch.cat([
            torch.linspace(1.0, 2.9, 12),
            torch.full((12,), 3.0),
            torch.linspace(3.1, 10.0, 8),
        ])
        self.depth = col.view(1, 32, 1).expand(3, 32, 32).contiguous()

    def tearDown(self):
        if self._old_device is None:
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
        else:
            os.environ["OPEN_OPTICS_DEVICE"] = self._old_device
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _run(self, dev, quality, colorspace, max_radius_px):
        os.environ["OPEN_OPTICS_DEVICE"] = dev
        node = NODE_CLASS_MAPPINGS["OpenOptics_DepthOfField"]()
        return node.apply(
            self.image.clone(), depth_mask=self.depth.clone(), focal_mm=50, f_number=2.0,
            focus_m=3.0, sensor_width_mm=36, quality=quality, max_radius_px=max_radius_px,
            colorspace=colorspace, chunk_frames=2,
        )

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_dof_settings_parity(self):
        for quality in ("draft", "normal"):
            for colorspace in ("srgb", "linear"):
                for radius in (0, 4, 12):
                    with self.subTest(quality=quality, colorspace=colorspace, radius=radius):
                        cpu = self._run("cpu", quality, colorspace, radius)
                        gpu = self._run("cuda", quality, colorspace, radius)
                        for a, b in zip(cpu, gpu):
                            for t in (a, b):
                                self.assertTrue(torch.isfinite(t).all().item())
                                self.assertEqual(t.device.type, "cpu")
                                self.assertEqual(t.dtype, torch.float32)
                            self.assertLess((a - b).abs().max().item(), 1e-4)
                        for img in (cpu[0], gpu[0]):
                            self.assertGreaterEqual(img.min().item(), 0.0)
                            self.assertLessEqual(img.max().item(), 1.0)

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_dof_focus_plane_unchanged(self):
        for colorspace in ("srgb", "linear"):
            with self.subTest(colorspace=colorspace):
                img = self._run("cuda", "normal", colorspace, 3)[0]
                diff = (img[:, 15:21] - self.image[:, 15:21]).abs().max().item()
                self.assertLess(diff, 1e-4)


if __name__ == "__main__":
    unittest.main()
