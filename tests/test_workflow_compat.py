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


def order_problems(key, spec, expected):
    """Return a list of strings describing added inputs of node `key` that are misplaced.

    `spec` is an INPUT_TYPES() dict and `expected` the fixture entry. An added input is one
    whose name is not a first-release name. Added 'required' inputs are problems, and in
    'optional' the first-release names must come first, in order. No units apply.
    """
    problems = []
    old_names = {e[0] for s in ("required", "optional") for e in expected.get(s, [])}
    for name in spec.get("required", {}):
        if name not in old_names:
            problems.append(
                f"{key}: added input '{name}' is in 'required'; it must be optional")
    want = [e[0] for e in expected.get("optional", [])]
    current = list(spec.get("optional", {}))
    for i, name in enumerate(current[:len(want)]):
        if name not in old_names:
            problems.append(
                f"{key}: added input '{name}' comes before first-release input '{want[i]}'")
    return problems


def combo_problems(key, spec, expected):
    """Return a list of strings describing added combo inputs of node `key` with a bad default.

    `spec` is an INPUT_TYPES() dict and `expected` the fixture entry. An added combo is an
    input not in the fixture whose type is a list/tuple of choices; it needs an options dict
    whose 'default' is the first choice. No units apply.
    """
    problems = []
    old_names = {e[0] for s in ("required", "optional") for e in expected.get(s, [])}
    for section in ("required", "optional"):
        for name, value in spec.get(section, {}).items():
            if name in old_names:
                continue
            if not isinstance(value, (tuple, list)) or not isinstance(value[0], (list, tuple)):
                continue
            choices = list(value[0])
            opts = value[1] if len(value) > 1 and isinstance(value[1], dict) else {}
            if "default" not in opts:
                problems.append(f"{key}: added combo '{name}' has no default")
            elif choices and opts["default"] != choices[0]:
                problems.append(
                    f"{key}: added combo '{name}' default '{opts['default']}' "
                    f"is not its first choice '{choices[0]}'")
    return problems


class AddedComboDefaultTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.fixture = json.load(f)

    def test_added_combos_default_to_first_choice(self):
        problems = []
        for key, expected in self.fixture.items():
            spec = NODE_CLASS_MAPPINGS[key].INPUT_TYPES()
            problems += combo_problems(key, spec, expected)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_bad_combo_is_reported(self):
        key = "OpenOptics_DepthToMetric"
        expected = self.fixture[key]
        spec = copy.deepcopy(NODE_CLASS_MAPPINGS[key].INPUT_TYPES())
        spec.setdefault("optional", {})
        spec["optional"]["nodef"] = (["a", "b"],)
        spec["optional"]["second"] = (["a", "b"], {"default": "b"})
        problems = combo_problems(key, spec, expected)
        self.assertTrue(any(key in p and "nodef" in p for p in problems), problems)
        self.assertTrue(any(key in p and "second" in p for p in problems), problems)


class AddedInputOrderTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.fixture = json.load(f)

    def test_added_inputs_after_first_release(self):
        problems = []
        for key, expected in self.fixture.items():
            spec = NODE_CLASS_MAPPINGS[key].INPUT_TYPES()
            problems += order_problems(key, spec, expected)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_added_before_first_release_is_reported(self):
        key = "OpenOptics_DepthToMetric"
        expected = self.fixture[key]
        self.assertTrue(expected.get("optional"), "fixture needs first-release optional inputs")
        spec = copy.deepcopy(NODE_CLASS_MAPPINGS[key].INPUT_TYPES())
        spec["optional"] = {"zzz": ("FLOAT", {"default": 0.0}), **spec["optional"]}
        problems = order_problems(key, spec, expected)
        self.assertTrue(any(key in p and "zzz" in p for p in problems), problems)

        spec = copy.deepcopy(NODE_CLASS_MAPPINGS[key].INPUT_TYPES())
        spec["required"]["zzz"] = ("FLOAT", {"default": 0.0})
        problems = order_problems(key, spec, expected)
        self.assertTrue(any(key in p and "zzz" in p for p in problems), problems)


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


def _is_link(value):
    """Return True if `value` is an API link [str node id, int slot]. No units apply."""
    return (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)
            and isinstance(value[1], int) and not isinstance(value[1], bool))


def validate_api_graph(graph, nodes=None):
    """Return a list of error strings for an API-format graph (dict of id -> node entry).

    `nodes` maps class_type to node class (default NODE_CLASS_MAPPINGS); entries whose
    class_type is not in it are ignored. Checks required inputs, links, types and ranges.
    No units apply.
    """
    nodes = NODE_CLASS_MAPPINGS if nodes is None else nodes
    errors = []
    for node_id, entry in graph.items():
        cls_name = entry.get("class_type")
        if cls_name not in nodes:
            continue
        who = f"{node_id} {cls_name}"
        spec = nodes[cls_name].INPUT_TYPES()
        inputs = entry.get("inputs", {})
        for name in spec.get("required", {}):
            if name not in inputs:
                errors.append(f"{who}: Required input is missing: {name}")
        declared = {**spec.get("optional", {}), **spec.get("required", {})}
        for name, value in inputs.items():
            if name not in declared:
                continue
            decl = declared[name]
            typ = decl[0]
            opts = decl[1] if len(decl) > 1 and isinstance(decl[1], dict) else {}
            if _is_link(value):
                src = graph.get(value[0])
                if src is not None and src.get("class_type") in nodes:
                    rt = nodes[src["class_type"]].RETURN_TYPES
                    got = rt[value[1]] if value[1] < len(rt) else None
                    if got != typ:
                        errors.append(
                            f"{who}: input {name} of type {typ} is linked to "
                            f"{value[0]} {src['class_type']} slot {value[1]} "
                            f"which returns {got}")
                continue
            if typ in ("IMAGE", "MASK"):
                errors.append(f"{who}: input {name} expects a link, got {value!r}")
            elif typ in ("FLOAT", "INT"):
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors.append(f"{who}: input {name} must be a number, got {value!r}")
                    continue
                if typ == "INT" and not isinstance(value, int):
                    errors.append(f"{who}: input {name} must be an int, got {value!r}")
                if "min" in opts and value < opts["min"]:
                    errors.append(f"{who}: input {name} value {value!r} is below min {opts['min']}")
                if "max" in opts and value > opts["max"]:
                    errors.append(f"{who}: input {name} value {value!r} is above max {opts['max']}")
            elif typ == "BOOLEAN":
                if not isinstance(value, bool):
                    errors.append(f"{who}: input {name} must be a bool, got {value!r}")
            elif isinstance(typ, (list, tuple)):
                if value not in typ:
                    errors.append(
                        f"{who}: input {name} value {value!r} is not in {list(typ)}")
    return errors


class ApiValidatorTest(unittest.TestCase):
    def _graph(self):
        return {
            "1": {"class_type": "LoadImage", "inputs": {"image": "a.png"}},
            "2": {"class_type": "OpenOptics_Vignette",
                  "inputs": {"image": ["1", 0], "focal_mm": 35.0, "sensor_width_mm": 36.0,
                             "strength": 0.5, "colorspace": "srgb"}},
        }

    def test_valid_graph_has_no_errors(self):
        self.assertEqual(validate_api_graph(self._graph()), [])

    def test_unknown_class_is_ignored(self):
        graph = {"9": {"class_type": "NotAnOpenOpticsNode", "inputs": {}}}
        self.assertEqual(validate_api_graph(graph), [])


if __name__ == "__main__":
    unittest.main()
