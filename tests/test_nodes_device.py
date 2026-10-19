"""Tests for open_optics_nodes.device.get_device."""

import os
import sys
import types
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


def _fake_comfy(device):
    """Return (modules, calls): fake comfy modules whose device is `device`."""
    calls = []

    def get_torch_device():
        calls.append(1)
        return device

    comfy = types.ModuleType("comfy")
    mm = types.ModuleType("comfy.model_management")
    mm.get_torch_device = get_torch_device
    comfy.model_management = mm
    return {"comfy": comfy, "comfy.model_management": mm}, calls


class AutoModeTests(unittest.TestCase):
    def test_auto_uses_comfy_device(self):
        device = torch.device("cpu")
        modules, calls = _fake_comfy(device)
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "auto"}):
            with mock.patch.dict(sys.modules, modules):
                result = get_device()
        self.assertIs(result, device)
        self.assertEqual(len(calls), 1)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA not available")
    def test_auto_uses_comfy_device_cuda(self):
        device = torch.device("cuda")
        modules, calls = _fake_comfy(device)
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "auto"}):
            with mock.patch.dict(sys.modules, modules):
                result = get_device()
        self.assertIs(result, device)
        self.assertEqual(len(calls), 1)

    def _auto_without_comfy(self, cuda, env):
        absent = {"comfy": None, "comfy.model_management": None}
        with mock.patch.dict(os.environ, env):
            if not env:
                os.environ.pop("OPEN_OPTICS_DEVICE", None)
            with mock.patch.dict(sys.modules, absent):
                with mock.patch("torch.cuda.is_available", return_value=cuda):
                    return get_device()

    def test_auto_no_comfy_no_cuda_is_cpu(self):
        result = self._auto_without_comfy(False, {"OPEN_OPTICS_DEVICE": "auto"})
        self.assertEqual(result.type, "cpu")

    def test_auto_no_comfy_with_cuda_is_cuda(self):
        result = self._auto_without_comfy(True, {"OPEN_OPTICS_DEVICE": "auto"})
        self.assertEqual(result.type, "cuda")

    def test_auto_default_without_comfy(self):
        self.assertEqual(self._auto_without_comfy(False, {}).type, "cpu")
        self.assertEqual(self._auto_without_comfy(True, {}).type, "cuda")


if __name__ == "__main__":
    unittest.main()
