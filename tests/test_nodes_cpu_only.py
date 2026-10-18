"""The node package must stay on the CPU: no GPU device use anywhere."""

import os
import time
import unittest

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Built from pieces so the forbidden words are not spelled out here.
FORBIDDEN = [
    "." + "cuda(",
    "cu" + "da",
    "torch." + "compile",
    "device" + "=",
    '.to("' + "cuda",
    "m" + "ps",
    "pin_" + "memory",
]


def _node_files():
    files = [os.path.join(ROOT, "__init__.py")]
    for dirpath, _dirs, names in os.walk(os.path.join(ROOT, "open_optics_nodes")):
        for name in names:
            if name.endswith(".py"):
                files.append(os.path.join(dirpath, name))
    return files


class TestNodesCpuOnly(unittest.TestCase):
    def test_no_gpu_device_use(self):
        files = _node_files()
        self.assertGreaterEqual(len(files), 5)
        for path in files:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for word in FORBIDDEN:
                self.assertNotIn(word, text, f"{word!r} found in {path}")


def _defaults(cls):
    out = {}
    for name, spec in cls.INPUT_TYPES()["required"].items():
        if spec[0] in ("IMAGE", "MASK"):
            continue
        if isinstance(spec[0], list):
            out[name] = spec[0][0]
        else:
            out[name] = spec[1]["default"]
    return out


class TestNodesRunOnCpuQuickly(unittest.TestCase):
    def test_all_nodes_cpu_outputs_under_time_limit(self):
        torch.manual_seed(7)
        image = torch.rand(1, 64, 64, 3, dtype=torch.float32)
        depth = 0.5 + 7.5 * torch.rand(1, 64, 64, dtype=torch.float32)
        self.assertEqual(len(NODE_CLASS_MAPPINGS), 7)
        start = time.perf_counter()
        for key, cls in NODE_CLASS_MAPPINGS.items():
            kwargs = _defaults(cls)
            if "image" in cls.INPUT_TYPES()["required"]:
                kwargs["image"] = image
            if "depth_mask" in cls.INPUT_TYPES().get("optional", {}):
                kwargs["depth_mask"] = depth
            outputs = getattr(cls(), cls.FUNCTION)(**kwargs)
            for t in outputs:
                self.assertEqual(t.device.type, "cpu", key)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 10.0)


if __name__ == "__main__":
    unittest.main()
