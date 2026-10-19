"""Each node logs exactly one INFO record per call and prints nothing."""

import contextlib
import io
import os
import re
import unittest
from unittest import mock

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS

B, H, W = 3, 12, 16
CHUNK = 2


def _inputs():
    torch.manual_seed(7)
    image = torch.rand(B, H, W, 3, dtype=torch.float32)
    depth = 0.5 + 7.5 * torch.rand(B, H, W, dtype=torch.float32)
    return image, depth


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
    if "chunk_frames" in types["required"] or "chunk_frames" in types.get("optional", {}):
        kwargs["chunk_frames"] = CHUNK
    return kwargs


class TestNodeLogging(unittest.TestCase):
    def _check_all(self, device_env, device_name):
        image, depth = _inputs()
        for key, cls in NODE_CLASS_MAPPINGS.items():
            with self.subTest(node=key, device=device_env):
                layers = r"( layers=\d+)" if key == "OpenOptics_DepthOfField" else ""
                pattern = re.compile(
                    rf"^node={key} device={re.escape(device_name)} frames={B} "
                    rf"chunk_frames={CHUNK} seconds=\d+\.\d{{3}}{layers}$")
                node = cls()
                kwargs = _kwargs(cls, image, depth)
                out = io.StringIO()
                with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": device_env}), \
                        self.assertLogs("open_optics_nodes", "INFO") as logs, \
                        contextlib.redirect_stdout(out):
                    result = getattr(node, cls.FUNCTION)(**kwargs)
                self.assertEqual(len(logs.records), 1)
                self.assertRegex(logs.records[0].getMessage(), pattern)
                self.assertEqual(out.getvalue(), "")
                for t in result:
                    self.assertIsInstance(t, torch.Tensor)
                    self.assertEqual(t.device.type, "cpu")
                    self.assertEqual(t.shape[0], B)

    def test_all_nodes_log_one_record_on_cpu(self):
        self.assertEqual(len(NODE_CLASS_MAPPINGS), 8)
        self._check_all("cpu", "cpu")

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is not available")
    def test_all_nodes_log_one_record_on_cuda(self):
        try:
            self._check_all("cuda", "cuda:0")
        finally:
            torch.cuda.empty_cache()


if __name__ == "__main__":
    unittest.main()
