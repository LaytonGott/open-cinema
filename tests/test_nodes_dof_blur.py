import os
import unittest
from unittest import mock

import torch
import torch.nn.functional as F

from open_optics_nodes import dof_blur
from open_optics_nodes.device import get_device


class DofBlurTest(unittest.TestCase):
    def test_radius_one_kernel(self):
        k = dof_blur.disc_kernel(1.0)
        self.assertEqual(tuple(k.shape), (3, 3))
        for i, j in ((0, 0), (0, 2), (2, 0), (2, 2)):
            self.assertAlmostEqual(k[i, j].item(), 0.0, places=6)
        for i, j in ((1, 1), (0, 1), (1, 0), (1, 2), (2, 1)):
            self.assertAlmostEqual(k[i, j].item(), 0.2, places=6)

    def test_kernel_on_device_argument(self):
        k = dof_blur.disc_kernel(2.0, device=torch.device("cpu"))
        self.assertEqual(tuple(k.shape), (5, 5))
        self.assertAlmostEqual(k.sum().item(), 1.0, delta=1e-6)
        self.assertAlmostEqual(k[2, 2].item(), 1.0 / 13.0, delta=1e-6)

    def test_kernel_sums_to_one(self):
        for r in (0.3, 1.0, 2.5, 4.0):
            self.assertAlmostEqual(dof_blur.disc_kernel(r).sum().item(), 1.0, places=6)

    def test_small_radius_unchanged(self):
        x = torch.rand(1, 2, 5, 5)
        self.assertTrue(torch.equal(dof_blur.blur_layer(x, 0.3), x))

    def test_constant_image(self):
        x = torch.full((1, 1, 6, 6), 0.7)
        out = dof_blur.blur_layer(x, 2.0)
        self.assertEqual(out.shape, x.shape)
        self.assertTrue(torch.allclose(out, x, atol=1e-5))

    def test_single_pixel(self):
        x = torch.zeros(1, 1, 5, 5)
        x[0, 0, 2, 2] = 1.0
        out = dof_blur.blur_layer(x, 1.0)
        for i, j in ((2, 2), (1, 2), (3, 2), (2, 1), (2, 3)):
            self.assertAlmostEqual(out[0, 0, i, j].item(), 0.2, delta=1e-6)
        self.assertAlmostEqual(out[0, 0, 1, 1].item(), 0.0, delta=1e-6)

    @unittest.skipUnless(torch.cuda.is_available(), "needs CUDA")
    def test_cpu_matches_cuda(self):
        g = torch.Generator().manual_seed(0)
        x = torch.rand(1, 3, 24, 24, generator=g, dtype=torch.float32)
        cpu = dof_blur.blur_layer(x, 3.0)
        gpu = dof_blur.blur_layer(x.to(torch.device("cuda")), 3.0)
        self.assertEqual(gpu.device.type, "cuda")
        self.assertLess((cpu - gpu.cpu()).abs().max().item(), 1e-4)
        del gpu
        torch.cuda.empty_cache()

    def _devices(self):
        for name in ("cpu", "cuda"):
            if name == "cuda" and not torch.cuda.is_available():
                continue
            with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": name}):
                yield get_device()

    def test_fft_matches_direct_conv(self):
        g = torch.Generator().manual_seed(1)
        x0 = torch.rand(1, 4, 40, 48, generator=g, dtype=torch.float32)
        for device in self._devices():
            x = x0.to(device)
            out = dof_blur.blur_layer(x, 6.5)
            pad = 7
            kernel = dof_blur.disc_kernel(6.5, device)
            weight = kernel[None, None].repeat(4, 1, 1, 1)
            padded = F.pad(x, (pad, pad, pad, pad), mode="replicate")
            ref = F.conv2d(padded, weight, groups=4)
            self.assertLess((out - ref).abs().max().item(), 1e-5)
            del out, ref, x
            if device.type == "cuda":
                torch.cuda.empty_cache()

    def test_fft_shape_and_dtype(self):
        x0 = torch.rand(2, 3, 20, 31, dtype=torch.float32)
        for device in self._devices():
            out = dof_blur.blur_layer(x0.to(device), 5.0)
            self.assertEqual(tuple(out.shape), (2, 3, 20, 31))
            self.assertEqual(out.dtype, torch.float32)
            self.assertEqual(out.device.type, device.type)
            del out
            if device.type == "cuda":
                torch.cuda.empty_cache()


if __name__ == "__main__":
    unittest.main()
