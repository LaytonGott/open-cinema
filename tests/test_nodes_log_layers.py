"""Only Depth of Field logs a layers field, and it is an integer >= 1."""

import os
import re
import unittest
from unittest import mock

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS

B, H, W = 3, 12, 16


def _kwargs(cls, image, depth):
    types = cls.INPUT_TYPES()
    kwargs = {}
    for name, spec in types["required"].items():
        if name == "image":
            kwargs[name] = image
        elif name == "depth":
            kwargs[name] = depth
        elif isinstance(spec[0], list):
            kwargs[name] = spec[0][0]
        else:
            kwargs[name] = spec[1]["default"]
    if "depth_mask" in types.get("optional", {}):
        kwargs["depth_mask"] = depth
    return kwargs


class TestLogLayers(unittest.TestCase):
    def test_layers_only_on_depth_of_field(self):
        torch.manual_seed(7)
        image = torch.rand(B, H, W, 3, dtype=torch.float32)
        depth = 0.5 + 7.5 * torch.rand(B, H, W, dtype=torch.float32)
        self.assertEqual(len(NODE_CLASS_MAPPINGS), 8)
        for key, cls in NODE_CLASS_MAPPINGS.items():
            with self.subTest(node=key):
                kwargs = _kwargs(cls, image, depth)
                with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cpu"}), \
                        self.assertLogs("open_optics_nodes", "INFO") as logs:
                    getattr(cls(), cls.FUNCTION)(**kwargs)
                self.assertEqual(len(logs.records), 1)
                message = logs.records[0].getMessage()
                if key == "OpenOptics_DepthOfField":
                    match = re.search(r" layers=(\d+)$", message)
                    self.assertIsNotNone(match, message)
                    self.assertGreaterEqual(int(match.group(1)), 1)
                else:
                    self.assertNotIn("layers", message)


if __name__ == "__main__":
    unittest.main()
