"""Image nodes on odd sizes and batch splits (CPU)."""

import os
import unittest
from unittest import mock

import torch

from open_optics_nodes import NODE_CLASS_MAPPINGS

NODE_NAMES = (
    "OpenOptics_Anamorphic",
    "OpenOptics_ChromaticAberration",
    "OpenOptics_FocalCrop",
    "OpenOptics_LensDistortion",
    "OpenOptics_Vignette",
)


def _kwargs(cls, image):
    kwargs = {}
    for name, spec in cls.INPUT_TYPES()["required"].items():
        if spec[0] == "IMAGE":
            kwargs[name] = image
        elif isinstance(spec[0], list):
            kwargs[name] = spec[0][0]
        else:
            kwargs[name] = spec[1]["default"]
    return kwargs


class TestImageNodeEdgeCases(unittest.TestCase):
    def _run(self, name, image, chunk_frames):
        cls = NODE_CLASS_MAPPINGS[name]
        kwargs = _kwargs(cls, image)
        kwargs["chunk_frames"] = chunk_frames
        out = getattr(cls(), cls.FUNCTION)(**kwargs)[0]
        return out

    def _check(self, name, frames, chunk_frames, full_chunk):
        torch.manual_seed(0)
        image = torch.rand(frames, 9, 13, 3, dtype=torch.float32)
        original = image.clone()
        full = self._run(name, image, full_chunk)
        out = self._run(name, image, chunk_frames)
        self.assertEqual(out.shape[0], frames)
        self.assertEqual(full.shape[0], frames)
        self.assertEqual(out.shape[1:3], full.shape[1:3])
        self.assertLessEqual((out - full).abs().max().item(), 1e-5)
        self.assertTrue(torch.equal(image, original))

    def test_edge_cases(self):
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cpu"}):
            for name in NODE_NAMES:
                with self.subTest(node=name, case="one frame"):
                    self._check(name, 1, 8, 1)
                with self.subTest(node=name, case="chunk 2 of 5"):
                    self._check(name, 5, 2, 5)
                with self.subTest(node=name, case="chunk 100 of 3"):
                    self._check(name, 3, 100, 3)


if __name__ == "__main__":
    unittest.main()
