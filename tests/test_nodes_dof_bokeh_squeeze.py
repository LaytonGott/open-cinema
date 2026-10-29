import unittest

import torch

from open_optics_nodes import dof_blur
from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField


class BokehSqueezeTest(unittest.TestCase):
    def test_kernel_shape_and_sum(self):
        # radius 6, squeeze 2: height 2 * 6 + 1 = 13, width 2 * ceil(6 / 2) + 1 = 7
        k = dof_blur.disc_kernel(6.0, squeeze=2.0)
        self.assertEqual(tuple(k.shape), (13, 7))
        self.assertAlmostEqual(k.sum().item(), 1.0, places=6)

    def test_squeeze_one_is_the_disc(self):
        self.assertTrue(torch.equal(dof_blur.disc_kernel(4.5), dof_blur.disc_kernel(4.5, squeeze=1.0)))

    def test_fft_and_conv_agree_for_an_ellipse(self):
        x = torch.rand((1, 4, 20, 24), generator=torch.Generator().manual_seed(2))
        big = dof_blur.blur_layer(x, 5.0, 1.5)  # FFT path (radius >= 4)
        k = dof_blur.disc_kernel(5.0, squeeze=1.5)
        padded = torch.nn.functional.pad(x, (4, 4, 5, 5), mode="replicate")
        ref = torch.nn.functional.conv2d(padded, k[None, None].repeat(4, 1, 1, 1), groups=4)
        self.assertTrue(torch.allclose(big, ref, atol=1e-5))

    def test_oval_bokeh_from_the_node(self):
        dot = torch.zeros((1, 61, 61, 3))
        dot[0, 30, 30, :] = 1.0
        far = torch.full((1, 61, 61), 1000.0)
        args = dict(image=dot, focal_mm=50.0, f_number=1.4, focus_m=1.0, sensor_width_mm=4.0, quality="normal",
                    max_radius_px=12, colorspace="linear", depth_mask=far)
        node = OpenOptics_DepthOfField()
        for squeeze, (h, w) in ((1.0, (25, 25)), (2.0, (25, 13))):
            m = node.apply(**args, bokeh_squeeze=squeeze)[0][0, :, :, 0] > 1e-6
            rows = torch.nonzero(m.any(dim=1)).flatten()
            cols = torch.nonzero(m.any(dim=0)).flatten()
            self.assertEqual((int(rows.max() - rows.min() + 1), int(cols.max() - cols.min() + 1)), (h, w))

    def test_out_of_range(self):
        node = OpenOptics_DepthOfField()
        img = torch.rand((1, 8, 8, 3))
        with self.assertRaises(ValueError):
            node.apply(image=img, depth_mask=torch.ones((1, 8, 8)), bokeh_squeeze=2.5)


if __name__ == "__main__":
    unittest.main()
