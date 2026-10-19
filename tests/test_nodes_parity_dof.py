import os
import unittest

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS


class TestDepthOfFieldParity(unittest.TestCase):
    def setUp(self):
        self._old_device = os.environ.get("OPEN_OPTICS_DEVICE")
        torch.manual_seed(7)
        self.image = torch.rand(4, 40, 40, 3)
        self.depth = torch.full((4, 40, 40), 10.0)
        self.depth[:, :, :20] = 3.0

    def tearDown(self):
        if self._old_device is None:
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
        else:
            os.environ["OPEN_OPTICS_DEVICE"] = self._old_device
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _run(self, dev):
        os.environ["OPEN_OPTICS_DEVICE"] = dev
        node = NODE_CLASS_MAPPINGS["OpenOptics_DepthOfField"]()
        return node.apply(
            self.image.clone(), depth_mask=self.depth.clone(), focal_mm=50, f_number=2.0,
            focus_m=3.0, sensor_width_mm=36, quality="normal", max_radius_px=8,
            chunk_frames=3,
        )

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_dof_parity(self):
        cpu = self._run("cpu")
        gpu = self._run("cuda")
        self.assertEqual(len(cpu), len(gpu))
        for a, b in zip(cpu, gpu):
            self.assertEqual(a.device.type, "cpu")
            self.assertEqual(b.device.type, "cpu")
            self.assertEqual(a.shape, b.shape)
            self.assertLess((a - b).abs().max().item(), 1e-4)

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_dof_blurs_far_region(self):
        img, coc = self._run("cuda")

        def roughness(cols):
            region = img[:, :, cols, :]
            return (region[:, :, 1:, :] - region[:, :, :-1, :]).abs().mean().item()

        self.assertLess(roughness(slice(26, 38)), roughness(slice(2, 15)))
        self.assertGreater(coc[:, :, 26:38].mean().item(), coc[:, :, 2:15].mean().item())


if __name__ == "__main__":
    unittest.main()
