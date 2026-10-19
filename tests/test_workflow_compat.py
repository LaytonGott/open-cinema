"""Saved workflows store widget values by position, so first-release inputs must not change."""
import copy
import json
import os
import unittest

import open_optics_nodes
from open_optics_nodes import NODE_CLASS_MAPPINGS

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "first_release_inputs.json")


def _entry(name, value):
    """Return [name, type, opts] as JSON-style lists; opts is {} when absent."""
    value = list(value) if isinstance(value, (tuple, list)) else [value]
    opts = value[1] if len(value) > 1 else {}
    return json.loads(json.dumps([name, value[0], opts]))


def first_release_problems(key, spec, expected):
    """Return a list of strings describing first-release inputs of node `key` that changed.

    `spec` is an INPUT_TYPES() dict and `expected` the fixture entry with 'required' and
    'optional' lists of [name, type, opts]. Added inputs after the first-release ones are
    allowed, except in 'required', where the lengths must match. No units apply.
    """
    problems = []
    for section in ("required", "optional"):
        want = expected.get(section, [])
        current = [_entry(n, v) for n, v in spec.get(section, {}).items()]
        for i, exp in enumerate(want):
            got = current[i] if i < len(current) else None
            if got != exp:
                problems.append(
                    f"{key}: first-release input '{exp[0]}' changed "
                    f"(expected {exp}, got {got}) in {section}")
        if section == "required" and len(current) != len(want):
            extra = [c[0] for c in current[len(want):]]
            problems.append(
                f"{key}: required inputs differ in count (expected {len(want)}, "
                f"got {len(current)}; extra {extra})")
    return problems


class FirstReleaseInputsTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.fixture = json.load(f)
        self.key = "OpenOptics_LensDistortion"
        self.spec = copy.deepcopy(NODE_CLASS_MAPPINGS[self.key].INPUT_TYPES())

    def _section_of(self, name):
        for section in ("required", "optional"):
            if name in self.spec.get(section, {}):
                return section
        self.fail(f"{name} not found")

    def test_all_fixture_nodes_unchanged(self):
        problems = []
        for key, expected in self.fixture.items():
            self.assertIn(key, NODE_CLASS_MAPPINGS)
            spec = NODE_CLASS_MAPPINGS[key].INPUT_TYPES()
            problems += first_release_problems(key, spec, expected)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_renaming_is_detected(self):
        section = self._section_of("k1")
        self.spec[section] = {("k1_renamed" if n == "k1" else n): v
                              for n, v in self.spec[section].items()}
        problems = first_release_problems(self.key, self.spec, self.fixture[self.key])
        self.assertTrue(any(self.key in p and "'k1'" in p for p in problems), problems)

    def test_retyping_is_detected(self):
        section = self._section_of("p1")
        old = self.spec[section]["p1"]
        opts = old[1] if isinstance(old, (tuple, list)) and len(old) > 1 else {}
        self.spec[section]["p1"] = ("INT", opts)
        problems = first_release_problems(self.key, self.spec, self.fixture[self.key])
        self.assertTrue(any(self.key in p and "'p1'" in p for p in problems), problems)

    def test_reordering_is_detected(self):
        section = self._section_of("k2")
        self.assertEqual(section, self._section_of("k3"))
        items = list(self.spec[section].items())
        names = [n for n, _ in items]
        i, j = names.index("k2"), names.index("k3")
        items[i], items[j] = items[j], items[i]
        self.spec[section] = dict(items)
        problems = first_release_problems(self.key, self.spec, self.fixture[self.key])
        self.assertTrue(any(self.key in p and "'k2'" in p for p in problems), problems)
        self.assertTrue(any(self.key in p and "'k3'" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
