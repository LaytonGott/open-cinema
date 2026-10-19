import os
import unittest
from unittest import mock

import torch

from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField

B, H, W = 8, 48, 64
SUBJECT = (slice(16, 32), slice(26, 42))     # rows, cols; depth 3.0 m (in focus)
FOREGROUND = (slice(14, 34), slice(4, 20))   # depth 1.2 m (blurred)
FAR_GROUND = (slice(40, 48), slice(24, 44))  # bottom rows, depth about 8.6 to 10 m


def make_scene():
    gen = torch.Generator().manual_seed(1234)
    ys = torch.arange(H, dtype=torch.float32).view(H, 1)
    xs = torch.arange(W, dtype=torch.float32).view(1, W)
    pattern = 0.5 + 0.25 * torch.sin(xs * 0.3) * torch.cos(ys * 0.2)
    image = pattern.view(1, H, W, 1).expand(B, H, W, 3).clone()
    image = image + 0.15 * torch.randn(B, H, W, 3, generator=gen)
    image = image.clamp(0.0, 1.0).contiguous()
    depth = torch.linspace(1.0, 10.0, H).view(1, H, 1).expand(B, H, W).clone()
    depth[(slice(None),) + SUBJECT] = 3.0
    depth[(slice(None),) + FOREGROUND] = 1.2
    return image, depth


def detail(img, region):
    """Mean absolute horizontal neighbour difference inside a region."""
    patch = img[(slice(None),) + region]
    return (patch[:, :, 1:] - patch[:, :, :-1]).abs().mean().item()


def run_dof(device, f_number=2.0, focal_mm=50.0):
    image, depth = make_scene()
    with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": device}):
        out, _ = OpenOptics_DepthOfField().apply(
            image, focal_mm=focal_mm, f_number=f_number, focus_m=3.0, sensor_width_mm=36.0,
            quality="normal", max_radius_px=32, colorspace="srgb", depth_mask=depth)
    return image, out


class DofQualityTest(unittest.TestCase):
    def check_quality(self, image, out):
        self.assertEqual(out.shape, image.shape)
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(out.device.type, "cpu")
        self.assertTrue(torch.isfinite(out).all().item())
        self.assertGreaterEqual(out.min().item(), 0.0)
        self.assertLessEqual(out.max().item(), 1.0)

    def test_detail_contrast(self):
        # At 50 mm f/2 on a 64 px wide frame the blur radius is about 0.5 px (36 mm
        # sensor, 3 m focus), too small to change the image, so this check uses
        # 100 mm f/0.5 (16x the radius). The in-focus subject keeps its noise; the
        # blurred regions average it away, so a ratio of 1.5 is a safe margin.
        _, out = run_dof("cpu", f_number=0.5, focal_mm=100.0)
        subject = detail(out, SUBJECT)
        self.assertGreater(subject, 1.5 * detail(out, FAR_GROUND))
        self.assertGreater(subject, 1.5 * detail(out, FOREGROUND))

    def test_cpu_quality(self):
        image, out = run_dof("cpu")
        self.check_quality(image, out)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA not available")
    def test_gpu_quality_and_parity(self):
        try:
            image, cpu_out = run_dof("cpu")
            _, gpu_out = run_dof("cuda")
            self.check_quality(image, gpu_out)
            self.assertLessEqual((gpu_out - cpu_out).abs().max().item(), 1e-4)
        finally:
            torch.cuda.empty_cache()

    def test_default_chunk_frames(self):
        spec = OpenOptics_DepthOfField.INPUT_TYPES()
        self.assertEqual(spec["required"]["chunk_frames"][1]["default"], 8)

    # Note: the full-size 8 GiB limit is checked by scripts/accept_gpu.py.
    @unittest.skipUnless(torch.cuda.is_available(), "CUDA not available")
    def test_default_chunk_peak_gpu_memory(self):
        frames = 16
        image, depth = make_scene()
        image = image.repeat(2, 1, 1, 1)[:frames].contiguous()
        depth = depth.repeat(2, 1, 1)[:frames].contiguous()
        try:
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cuda"}):
                out, _ = OpenOptics_DepthOfField().apply(
                    image, focal_mm=50.0, f_number=2.0, focus_m=3.0, sensor_width_mm=36.0,
                    quality="normal", max_radius_px=32, colorspace="srgb", depth_mask=depth)
            self.assertEqual(out.shape[0], frames)
            self.assertLess(torch.cuda.max_memory_allocated(), 1024 ** 3)
        finally:
            torch.cuda.empty_cache()


if __name__ == "__main__":
    unittest.main()
