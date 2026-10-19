import os
import unittest

import torch

from open_optics_nodes.depth_of_field import OpenOptics_DepthOfField
from open_optics_nodes.depth_to_metric import OpenOptics_DepthToMetric


class TestSubjectDepthFeedsDof(unittest.TestCase):
    def setUp(self):
        self._old_device = os.environ.get("OPEN_OPTICS_DEVICE")
        os.environ["OPEN_OPTICS_DEVICE"] = "cpu"

    def tearDown(self):
        if self._old_device is None:
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
        else:
            os.environ["OPEN_OPTICS_DEVICE"] = self._old_device

    def test_subject_depth_feeds_dof(self):
        depth = torch.full((1, 9, 9), 0.4)
        depth[0, 3:6, 3:6] = 0.8
        depth[0, 0, 0] = 1.6
        depth[0, 8, 8] = 0.1
        depth_m, _ = OpenOptics_DepthToMetric().convert(
            mode="subject", subject_m=2.0, near_m=0.5, far_m=10.0, subject_x=0.5,
            subject_y=0.5, subject_radius_px=1, depth_mask=depth)

        gen = torch.Generator().manual_seed(11)
        image = torch.rand(1, 9, 9, 3, generator=gen)
        out, coc = OpenOptics_DepthOfField().apply(
            image, focus_m=2.0, depth_mask=depth_m, max_radius_px=4)

        self.assertLess((out[0, 3:6, 3:6] - image[0, 3:6, 3:6]).abs().max().item(), 1e-6)
        self.assertEqual(coc[0, 3:6, 3:6].abs().max().item(), 0.0)
        self.assertGreater(coc[0, 1, 1].item(), 0.0)
        self.assertGreater(coc[0, 0, 0].item(), 0.0)
        self.assertGreater(coc[0, 8, 8].item(), 0.0)


if __name__ == "__main__":
    unittest.main()
