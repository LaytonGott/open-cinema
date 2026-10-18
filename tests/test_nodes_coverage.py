import os
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

NODE_TESTS = [
    ("test_nodes_focal_crop.py", "OpenOptics_FocalCrop"),
    ("test_nodes_depth_of_field.py", "OpenOptics_DepthOfField"),
    ("test_nodes_lens_distortion.py", "OpenOptics_LensDistortion"),
    ("test_nodes_vignette.py", "OpenOptics_Vignette"),
    ("test_nodes_chromatic_aberration.py", "OpenOptics_ChromaticAberration"),
    ("test_nodes_anamorphic.py", "OpenOptics_Anamorphic"),
    ("test_nodes_depth_to_metric.py", "OpenOptics_DepthToMetric"),
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


if __name__ == "__main__":
    unittest.main()
