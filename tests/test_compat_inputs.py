"""First-release inputs of changed nodes must keep names, order, types and defaults."""
import json
import os
import unittest

import open_optics_nodes

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "first_release_inputs.json")
KEYS = ("OpenOptics_DepthTemporalSmooth", "OpenOptics_DepthToMetric")


def _entry(name, value):
    """Return [name, type, opts] as JSON-style lists; opts is {} when absent."""
    value = list(value) if isinstance(value, (tuple, list)) else [value]
    opts = value[1] if len(value) > 1 else {}
    return json.loads(json.dumps([name, value[0], opts]))


class CompatInputsTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.fixture = json.load(f)

    def test_first_release_inputs_unchanged(self):
        for key in KEYS:
            spec = open_optics_nodes.NODE_CLASS_MAPPINGS[key].INPUT_TYPES()
            for section in ("required", "optional"):
                expected = self.fixture[key][section]
                current = [_entry(n, v) for n, v in spec.get(section, {}).items()]
                with self.subTest(node=key, section=section):
                    self.assertEqual(current[:len(expected)], expected)
                    if section == "required":
                        self.assertEqual(len(current), len(expected))


if __name__ == "__main__":
    unittest.main()
