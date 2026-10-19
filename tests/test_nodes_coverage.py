import os
import unittest

from open_optics_nodes import NODE_CLASS_MAPPINGS

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

NODE_TESTS = [
    ("test_nodes_focal_crop.py", "OpenOptics_FocalCrop"),
    ("test_nodes_depth_of_field.py", "OpenOptics_DepthOfField"),
    ("test_nodes_lens_distortion.py", "OpenOptics_LensDistortion"),
    ("test_nodes_vignette.py", "OpenOptics_Vignette"),
    ("test_nodes_chromatic_aberration.py", "OpenOptics_ChromaticAberration"),
    ("test_nodes_anamorphic.py", "OpenOptics_Anamorphic"),
    ("test_nodes_depth_to_metric.py", "OpenOptics_DepthToMetric"),
    ("test_nodes_depth_temporal_smooth.py", "OpenOptics_DepthTemporalSmooth"),
]


class TestNodeCoverage(unittest.TestCase):
    def test_every_node_has_tests(self):
        for filename, class_name in NODE_TESTS:
            with self.subTest(file=filename, node=class_name):
                path = os.path.join(TESTS_DIR, filename)
                self.assertTrue(os.path.exists(path), f"{filename} is missing")
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                self.assertIn(class_name, text)
                self.assertTrue(
                    "delta=" in text or "places=" in text,
                    f"{filename} has no tolerance (delta= or places=)",
                )
        self.assertTrue(
            os.path.exists(os.path.join(TESTS_DIR, "test_nodes_registration.py"))
        )

    def test_required_inputs_have_defaults(self):
        for key, cls in NODE_CLASS_MAPPINGS.items():
            for name, spec in cls.INPUT_TYPES()["required"].items():
                if spec[0] in ("IMAGE", "MASK"):
                    continue
                with self.subTest(node=key, input=name):
                    if isinstance(spec[0], list):
                        self.assertGreater(len(spec[0]), 0)
                        if len(spec) > 1 and "default" in spec[1]:
                            self.assertIn(spec[1]["default"], spec[0])
                    else:
                        self.assertGreater(len(spec), 1)
                        self.assertIsInstance(spec[1], dict)
                        self.assertIn("default", spec[1])

    def test_depth_inputs_are_optional(self):
        for key in ("OpenOptics_DepthOfField", "OpenOptics_DepthToMetric"):
            with self.subTest(node=key):
                types = NODE_CLASS_MAPPINGS[key].INPUT_TYPES()
                self.assertEqual(types["optional"]["depth_mask"][0], "MASK")
                self.assertEqual(types["optional"]["depth_image"][0], "IMAGE")
                self.assertNotIn("depth_mask", types["required"])
                self.assertNotIn("depth_image", types["required"])

    def test_no_test_skips(self):
        # skipUnless is allowed for the CUDA and benchmark tests.
        words = ["skip" + "Test", "skip" + "If"]
        for filename in sorted(os.listdir(TESTS_DIR)):
            if not filename.endswith(".py") or filename == "test_nodes_coverage.py":
                continue
            with self.subTest(file=filename):
                with open(os.path.join(TESTS_DIR, filename), encoding="utf-8") as f:
                    text = f.read()
                for word in words:
                    self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
