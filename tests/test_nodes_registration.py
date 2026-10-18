"""Tests for node registration and the root-level re-export."""

import importlib.util
import os
import sys
import unittest

import open_optics_nodes
from open_optics_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXPECTED_NAMES = {
    "OpenOptics_FocalCrop": "Open Optics: Focal Crop",
    "OpenOptics_DepthOfField": "Open Optics: Depth of Field",
    "OpenOptics_LensDistortion": "Open Optics: Lens Distortion",
    "OpenOptics_Vignette": "Open Optics: Vignette",
    "OpenOptics_ChromaticAberration": "Open Optics: Chromatic Aberration",
    "OpenOptics_Anamorphic": "Open Optics: Anamorphic Squeeze",
    "OpenOptics_DepthToMetric": "Open Optics: Depth to Metric",
    "OpenOptics_DepthTemporalSmooth": "Open Optics: Depth Temporal Smooth",
}


def _load_root():
    spec = importlib.util.spec_from_file_location(
        "open_cinema_root",
        os.path.join(REPO_ROOT, "__init__.py"),
        submodule_search_locations=[REPO_ROOT],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["open_cinema_root"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop("open_cinema_root", None)
    return module


class TestRegistration(unittest.TestCase):
    def test_class_mapping_keys(self):
        self.assertEqual(set(NODE_CLASS_MAPPINGS), set(EXPECTED_NAMES))

    def test_display_names(self):
        self.assertEqual(NODE_DISPLAY_NAME_MAPPINGS, EXPECTED_NAMES)

    def test_class_interface(self):
        for key, cls in NODE_CLASS_MAPPINGS.items():
            with self.subTest(node=key):
                self.assertEqual(cls.CATEGORY, "Open Optics")
                types = cls.INPUT_TYPES()
                self.assertIsInstance(types, dict)
                self.assertIn("required", types)
                self.assertIsInstance(cls.RETURN_TYPES, tuple)
                self.assertTrue(callable(getattr(cls, cls.FUNCTION)))

    def test_required_inputs_have_defaults(self):
        for key, cls in NODE_CLASS_MAPPINGS.items():
            for name, spec in cls.INPUT_TYPES()["required"].items():
                if spec[0] in ("IMAGE", "MASK"):
                    continue
                with self.subTest(node=key, input=name):
                    self.assertGreater(len(spec), 1)
                    self.assertIn("default", spec[1])

    def test_root_reexport(self):
        root = _load_root()
        self.assertEqual(set(root.NODE_CLASS_MAPPINGS), set(NODE_CLASS_MAPPINGS))
        self.assertEqual(
            {k: v.__name__ for k, v in root.NODE_CLASS_MAPPINGS.items()},
            {k: v.__name__ for k, v in NODE_CLASS_MAPPINGS.items()},
        )
        self.assertEqual(
            root.NODE_DISPLAY_NAME_MAPPINGS, open_optics_nodes.NODE_DISPLAY_NAME_MAPPINGS
        )


if __name__ == "__main__":
    unittest.main()
