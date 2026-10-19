"""Checks that the framing module is core-only and not registered as a ComfyUI node."""
import pathlib
import unittest

import open_optics_nodes

ROOT = pathlib.Path(__file__).resolve().parent.parent


class FramingIsNotANodeTest(unittest.TestCase):
    def test_no_mapping_key_mentions_framing(self):
        for mapping in (
            open_optics_nodes.NODE_CLASS_MAPPINGS,
            open_optics_nodes.NODE_DISPLAY_NAME_MAPPINGS,
        ):
            for key in mapping:
                lowered = key.lower()
                self.assertNotIn("framing", lowered)
                self.assertNotIn("subject_distance", lowered)

    def test_no_node_function_is_subject_distance_m(self):
        for name, cls in open_optics_nodes.NODE_CLASS_MAPPINGS.items():
            self.assertNotEqual(getattr(cls, "FUNCTION", None), "subject_distance_m", name)

    def test_framing_source_has_no_registration(self):
        text = (ROOT / "open_optics" / "framing.py").read_text(encoding="utf-8")
        self.assertNotIn("NODE_CLASS_MAPPINGS", text)

    def test_nodes_init_does_not_mention_framing(self):
        text = (ROOT / "open_optics_nodes" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("framing", text)


if __name__ == "__main__":
    unittest.main()
