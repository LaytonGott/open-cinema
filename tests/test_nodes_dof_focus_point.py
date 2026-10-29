import unittest

import torch

from open_optics.focus_pull import rack_focus_m
from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField, depth_at_point


def scene(frames=4):
    """A 32 x 40 frame: left half 2 m, right half 8 m, random colours."""
    g = torch.Generator().manual_seed(1)
    image = torch.rand((frames, 32, 40, 3), generator=g)
    depth = torch.full((frames, 32, 40), 2.0)
    depth[:, :, 20:] = 8.0
    return image, depth


class FocusPointTest(unittest.TestCase):
    def setUp(self):
        self.node = OpenOptics_DepthOfField()
        self.image, self.depth = scene()
        self.base = dict(image=self.image, focal_mm=50.0, f_number=1.4, focus_m=3.0, sensor_width_mm=36.0,
                         quality="normal", max_radius_px=6, colorspace="srgb", depth_mask=self.depth)

    def test_depth_at_point_window_median(self):
        depth = torch.full((1, 20, 20), 5.0)
        depth[0, 10, 10] = 1.0  # one odd value in the 3 x 3 window: the median ignores it
        self.assertEqual(depth_at_point(depth, 0.5, 0.5, 9.0), [5.0])

    def test_depth_at_point_falls_back_when_no_valid_depth(self):
        depth = torch.full((2, 10, 10), float("nan"))
        self.assertEqual(depth_at_point(depth, 0.5, 0.5, 4.0), [4.0, 4.0])

    def test_defaults_change_nothing(self):
        a = self.node.apply(**self.base)[0]
        b = self.node.apply(**self.base, focus_x=-1.0, focus_y=-1.0, rack_x=-1.0, rack_y=-1.0)[0]
        self.assertTrue(torch.equal(a, b))

    def test_focus_point_equals_focus_distance_there(self):
        left = self.node.apply(**self.base, focus_x=0.2, focus_y=0.5)[0]
        at2 = self.node.apply(**dict(self.base, focus_m=2.0))[0]
        self.assertTrue(torch.allclose(left, at2, atol=1e-6))

    def test_rack_per_frame_and_chunking(self):
        racked = self.node.apply(**self.base, focus_x=0.2, focus_y=0.5, rack_x=0.8, rack_y=0.5, chunk_frames=3)[0]
        single = self.node.apply(**self.base, focus_x=0.2, focus_y=0.5, rack_x=0.8, rack_y=0.5, chunk_frames=1)[0]
        self.assertTrue(torch.allclose(racked, single, atol=1e-6))
        for i in range(4):
            d = rack_focus_m(2.0, 8.0, i / 3, 0.2, 0.8)
            ref = self.node.apply(**dict(self.base, image=self.image[i:i + 1], depth_mask=self.depth[i:i + 1], focus_m=d))[0]
            self.assertTrue(torch.allclose(racked[i:i + 1], ref, atol=1e-5), f"frame {i}")

    def test_bad_points(self):
        for kwargs in ({"focus_x": 0.5, "focus_y": -1.0}, {"rack_x": 0.5, "rack_y": 0.5},
                       {"focus_x": 0.2, "focus_y": 0.5, "rack_x": 0.8, "rack_y": 0.5, "rack_start": 0.7, "rack_end": 0.3}):
            with self.assertRaises(ValueError, msg=str(kwargs)):
                self.node.apply(**self.base, **kwargs)


if __name__ == "__main__":
    unittest.main()
