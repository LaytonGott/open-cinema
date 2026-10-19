"""Tests for open_optics_nodes.device.get_device."""

import os
import unittest
from unittest import mock

import torch

from open_optics_nodes.device import get_device


class GetDeviceTests(unittest.TestCase):
    def test_cpu(self):
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cpu"}):
            self.assertEqual(get_device().type, "cpu")

    def test_cuda(self):
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cuda"}):
            if torch.cuda.is_available():
                self.assertEqual(get_device().type, "cuda")
            else:
                with self.assertRaises(ValueError):
                    get_device()

    def test_invalid_values(self):
        for value in ("gpu", "CUDA2"):
            with self.subTest(value=value):
                with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": value}):
                    with self.assertRaises(ValueError) as ctx:
                        get_device()
                message = str(ctx.exception)
                for word in ("cpu", "cuda", "auto"):
                    self.assertIn(word, message)

    def test_env_change_between_calls(self):
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cpu"}):
            self.assertEqual(get_device().type, "cpu")
            os.environ["OPEN_OPTICS_DEVICE"] = "gpu"
            with self.assertRaises(ValueError):
                get_device()

    def test_cuda_unavailable_error(self):
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cuda"}):
            with mock.patch("torch.cuda.is_available", return_value=False):
                with self.assertRaises(ValueError) as ctx:
                    get_device()
        message = str(ctx.exception)
        for word in ("CUDA", "cpu", "auto"):
            self.assertIn(word, message)

    def test_unset_behaves_as_auto(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
            with mock.patch("torch.cuda.is_available", return_value=False):
                self.assertEqual(get_device().type, "cpu")


if __name__ == "__main__":
    unittest.main()
