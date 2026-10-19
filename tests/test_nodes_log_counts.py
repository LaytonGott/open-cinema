"""The log record of every node reports the frame count and the chunk size."""

import os
import re
import unittest
from unittest import mock

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS

H, W = 12, 16


def _kwargs(cls, batch, chunk):
    torch.manual_seed(7)
    image = torch.rand(batch, H, W, 3, dtype=torch.float32)
    depth = 0.5 + 7.5 * torch.rand(batch, H, W, dtype=torch.float32)
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
    if "chunk_frames" in types["required"] or "chunk_frames" in types.get("optional", {}):
        kwargs["chunk_frames"] = chunk
    return kwargs


class TestNodeLogCounts(unittest.TestCase):
    def _check(self, batch, chunk):
        self.assertEqual(len(NODE_CLASS_MAPPINGS), 8)
        for key, cls in NODE_CLASS_MAPPINGS.items():
            with self.subTest(node=key, frames=batch, chunk_frames=chunk):
                kwargs = _kwargs(cls, batch, chunk)
                with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cpu"}), \
                        self.assertLogs("open_optics_nodes", "INFO") as logs:
                    getattr(cls(), cls.FUNCTION)(**kwargs)
                self.assertEqual(len(logs.records), 1)
                message = logs.records[0].getMessage()
                self.assertIn(f" frames={batch} ", message)
                self.assertIn(f" chunk_frames={chunk} ", message)
                self.assertEqual(int(re.search(r" frames=(\d+) ", message).group(1)), batch)
                self.assertEqual(int(re.search(r" chunk_frames=(\d+) ", message).group(1)), chunk)

    def test_three_frames_chunk_two(self):
        self._check(3, 2)

    def test_five_frames_chunk_five(self):
        self._check(5, 5)


if __name__ == "__main__":
    unittest.main()
