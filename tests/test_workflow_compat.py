"""Saved workflows store widget values by position, so first-release inputs must not change."""
import copy
import inspect
import json
import os
import unittest

import torch

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
                    f"(expected {exp}, got {got}) in {section}; "
                    "restore the first-release name, type and position")
        if section == "required" and len(current) != len(want):
            extra = [c[0] for c in current[len(want):]]
            problems.append(
                f"{key}: required inputs differ in count (expected {len(want)}, "
                f"got {len(current)}; extra {extra}); "
                "restore the first-release name, type and position")
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
                f"{key}: new input {name} is required; make it optional with a default")
    want = [e[0] for e in expected.get("optional", [])]
    current = list(spec.get("optional", {}))
    for i, name in enumerate(current[:len(want)]):
        if name not in old_names:
            problems.append(
                f"{key}: new input {name} comes before first-release input {want[i]}; "
                "append it after the existing inputs")
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
                problems.append(f"{key}: added combo '{name}' has no default; "
                    "add a default equal to the first choice")
            elif choices and opts["default"] != choices[0]:
                problems.append(
                    f"{key}: added combo '{name}' default '{opts['default']}' "
                    f"is not its first choice '{choices[0]}'; "
                    "set the default to the first choice")
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
        self.assertTrue(any(key in p and "nodef" in p
                            and "add a default equal to the first choice" in p
                            for p in problems), problems)
        self.assertTrue(any(key in p and "second" in p
                            and "set the default to the first choice" in p
                            for p in problems), problems)


def default_problems(key, cls, expected):
    """Return a list of strings describing added inputs of node class `cls` without a default.

    `expected` is the fixture entry for `key`. An added input is one whose name is not in it.
    It is a problem if it is 'required', if its options dict has no 'default' (combos too), or
    if the node function has no Python default for it or one that differs. No units apply.
    """
    problems = []
    spec = cls.INPUT_TYPES()
    old_names = {e[0] for s in ("required", "optional") for e in expected.get(s, [])}
    params = inspect.signature(getattr(cls, cls.FUNCTION)).parameters
    for section in ("required", "optional"):
        for name, value in spec.get(section, {}).items():
            if name in old_names:
                continue
            if section == "required":
                problems.append(
                    f"{key}: new input {name} is required; make it optional with a default")
            opts = value[1] if isinstance(value, (tuple, list)) and len(value) > 1 \
                and isinstance(value[1], dict) else {}
            if "default" not in opts:
                problems.append(
                    f"{key}: new input {name} has no default in INPUT_TYPES; add a default")
                continue
            param = params.get(name)
            if param is None or param.default is inspect.Parameter.empty:
                problems.append(
                    f"{key}: new input {name} has no Python default; "
                    "add a matching default to the node function")
            elif param.default != opts["default"]:
                problems.append(
                    f"{key}: new input {name} Python default {param.default!r} "
                    f"differs from INPUT_TYPES default {opts['default']!r}; "
                    "add a matching default to the node function")
    return problems


def return_problems(key, cls, expected):
    """Return a list of strings describing first-release outputs of `cls` that changed.

    `expected` is the fixture entry for `key`; its 'return_types' list holds the first-release
    outputs. It is a problem if cls.RETURN_TYPES does not start with those types in order.
    No units apply.
    """
    problems = []
    got = list(cls.RETURN_TYPES)
    for i, want in enumerate(expected.get("return_types", [])):
        have = got[i] if i < len(got) else None
        if have != want:
            problems.append(
                f"{key}: output {i} must be {want} (first release) but is {have}; "
                "add new outputs only at the end")
    return problems


def node_set_problems(fixture, nodes):
    """Return a list of strings, one per fixture key missing from the `nodes` class mapping.

    `fixture` is the first-release inputs dict keyed by node key. No units apply.
    """
    return [
        f"{key}: first-release node is not registered; restore it or re-register it "
        "in NODE_CLASS_MAPPINGS, never rename or remove it"
        for key in fixture if key not in nodes]


def all_compat_problems(fixture, nodes):
    """Return a list of strings from every compatibility checker for every fixture node in `nodes`.

    `fixture` is the first-release inputs dict keyed by node key; `nodes` is the class mapping.
    An error raised by one node's INPUT_TYPES is reported as "<key>: <error>" and the loop
    goes on, so one broken node never hides the others. No units apply.
    """
    problems = list(node_set_problems(fixture, nodes))
    for key, expected in fixture.items():
        if key not in nodes:
            continue
        cls = nodes[key]
        try:
            spec = cls.INPUT_TYPES()
            problems += first_release_problems(key, spec, expected)
            problems += order_problems(key, spec, expected)
            problems += combo_problems(key, spec, expected)
            problems += default_problems(key, cls, expected)
            problems += return_problems(key, cls, expected)
        except Exception as e:
            problems.append(f"{key}: {e}")
    return problems


class AllCompatTest(unittest.TestCase):
    def test_all_nodes_clean(self):
        with open(FIXTURE, encoding="utf-8") as f:
            fixture = json.load(f)
        problems = all_compat_problems(fixture, NODE_CLASS_MAPPINGS)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_one_failure_does_not_hide_others(self):
        with open(FIXTURE, encoding="utf-8") as f:
            fixture = json.load(f)

        def broken(base, name):
            class Broken(base):
                @classmethod
                def INPUT_TYPES(cls):
                    spec = copy.deepcopy(base.INPUT_TYPES())
                    spec.setdefault("required", {})[name] = spec["optional"].pop(name)
                    return spec
            return Broken

        nodes = dict(NODE_CLASS_MAPPINGS)
        nodes["OpenOptics_DepthOfField"] = broken(
            NODE_CLASS_MAPPINGS["OpenOptics_DepthOfField"], "max_layers")
        nodes["OpenOptics_Vignette"] = broken(
            NODE_CLASS_MAPPINGS["OpenOptics_Vignette"], "chunk_frames")
        problems = all_compat_problems(fixture, nodes)
        self.assertTrue(any("OpenOptics_DepthOfField" in p and "max_layers" in p
                            and "make it optional with a default" in p
                            for p in problems), problems)
        self.assertTrue(any("OpenOptics_Vignette" in p and "chunk_frames" in p
                            for p in problems), problems)
        unrelated = [p for p in problems
                     if "OpenOptics_DepthOfField" not in p and "OpenOptics_Vignette" not in p]
        self.assertEqual(unrelated, [])


class NodeSetProblemsTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.fixture = json.load(f)

    def test_registered_nodes_clean(self):
        self.assertEqual(node_set_problems(self.fixture, NODE_CLASS_MAPPINGS), [])

    def test_missing_node_is_reported(self):
        key = sorted(self.fixture)[0]
        nodes = {k: v for k, v in NODE_CLASS_MAPPINGS.items() if k != key}
        problems = node_set_problems(self.fixture, nodes)
        self.assertTrue(any(key in p for p in problems), problems)


class ReturnTypesTest(unittest.TestCase):
    KEY = "OpenOptics_DepthOfField"

    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.fixture = json.load(f)

    def test_all_nodes_keep_first_release_outputs(self):
        problems = []
        for key, expected in self.fixture.items():
            problems += return_problems(key, NODE_CLASS_MAPPINGS[key], expected)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_inserted_output_is_reported(self):
        base = NODE_CLASS_MAPPINGS[self.KEY]
        sub = type("Inserted", (base,), {"RETURN_TYPES": ("FLOAT",) + tuple(base.RETURN_TYPES)})
        problems = return_problems(self.KEY, sub, self.fixture[self.KEY])
        self.assertTrue(any(self.KEY in p for p in problems), problems)

    def test_appended_output_is_allowed(self):
        base = NODE_CLASS_MAPPINGS[self.KEY]
        sub = type("Appended", (base,), {"RETURN_TYPES": tuple(base.RETURN_TYPES) + ("FLOAT",)})
        self.assertEqual(return_problems(self.KEY, sub, self.fixture[self.KEY]), [])


class _CleanNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)},
                "optional": {"gain": ("FLOAT", {"default": 1.0})}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"

    def run(self, image, gain=1.0):
        return (image,)


class DefaultProblemsTest(unittest.TestCase):
    def test_default_problems_clean_case(self):
        expected = {"required": [["image", "IMAGE", {}]], "optional": []}
        self.assertEqual(default_problems("Clean", _CleanNode, expected), [])


class AddedInputDefaultsTest(unittest.TestCase):
    KEY = "OpenOptics_Vignette"

    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.expected = json.load(f)[self.KEY]
        self.base = NODE_CLASS_MAPPINGS[self.KEY]

    def assert_reported(self, cls, hint):
        problems = default_problems(self.KEY, cls, self.expected)
        self.assertTrue(any(self.KEY in p and "chunk_frames" in p and hint in p
                            for p in problems), problems)

    def test_required_added_input_is_reported(self):
        base = self.base

        class Required(base):
            @classmethod
            def INPUT_TYPES(cls):
                spec = copy.deepcopy(base.INPUT_TYPES())
                spec["required"]["chunk_frames"] = spec["optional"].pop("chunk_frames")
                return spec

        self.assert_reported(Required, "make it optional with a default")

    def test_missing_input_default_is_reported(self):
        base = self.base

        class NoDefault(base):
            @classmethod
            def INPUT_TYPES(cls):
                spec = copy.deepcopy(base.INPUT_TYPES())
                kind, opts = spec["optional"]["chunk_frames"][:2]
                spec["optional"]["chunk_frames"] = (
                    kind, {k: v for k, v in opts.items() if k != "default"})
                return spec

        self.assert_reported(NoDefault, "add a default")

    def test_missing_python_default_is_reported(self):
        base = self.base

        class NoPyDefault(base):
            def apply(self, image, chunk_frames):
                pass

        self.assert_reported(NoPyDefault, "add a matching default to the node function")


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
        self.assertTrue(any("append it after the existing inputs" in p for p in problems), problems)

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
        self.assertTrue(any("restore the first-release name, type and position" in p
                            for p in problems), problems)

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


def _is_widget(decl):
    """Return True if a declared input takes a widget slot in the UI. No units apply."""
    typ = decl[0]
    return typ in ("FLOAT", "INT", "BOOLEAN", "STRING") or isinstance(typ, (list, tuple))


def ui_to_api(workflow, nodes=None):
    """Convert a UI-format graph (keys 'nodes' and 'links') to an API-format dict.

    Only Open Optics nodes (those in `nodes`, default NODE_CLASS_MAPPINGS) get inputs;
    other nodes are kept as bare entries so links to them resolve. Widget values map by
    position to the widget inputs (required first, then optional, in declared order).
    No units apply.
    """
    nodes = NODE_CLASS_MAPPINGS if nodes is None else nodes
    links = {link[0]: link for link in workflow.get("links", [])}
    graph = {}
    for node in workflow.get("nodes", []):
        cls_name = node.get("type")
        entry = {"class_type": cls_name, "inputs": {}}
        graph[str(node["id"])] = entry
        if cls_name not in nodes:
            continue
        spec = nodes[cls_name].INPUT_TYPES()
        declared = {**spec.get("required", {}), **spec.get("optional", {})}
        widgets = [name for name, decl in declared.items() if _is_widget(decl)]
        for name, value in zip(widgets, node.get("widgets_values", [])):
            entry["inputs"][name] = value
        for slot in node.get("inputs", []):
            link = links.get(slot.get("link"))
            if slot.get("link") is not None and link is not None:
                entry["inputs"][slot["name"]] = [str(link[1]), link[2]]
    return graph


def validate_ui_graph(workflow):
    """Return a list of error strings for a UI-format graph. No units apply."""
    return validate_api_graph(ui_to_api(workflow))


class UiConverterTest(unittest.TestCase):
    def test_widget_values_map_by_position(self):
        workflow = {
            "nodes": [
                {"id": 1, "type": "LoadImage", "inputs": [], "widgets_values": ["a.png"]},
                {"id": 2, "type": "OpenOptics_Vignette",
                 "inputs": [{"name": "image", "type": "IMAGE", "link": 7}],
                 "widgets_values": [35.0, 36.0, 1.0, "srgb", 8]},
            ],
            "links": [[7, 1, 0, 2, 0, "IMAGE"]],
        }
        inputs = ui_to_api(workflow)["2"]["inputs"]
        self.assertEqual(inputs["focal_mm"], 35.0)
        self.assertEqual(inputs["sensor_width_mm"], 36.0)
        self.assertEqual(inputs["strength"], 1.0)
        self.assertEqual(inputs["colorspace"], "srgb")
        self.assertEqual(inputs["chunk_frames"], 8)
        self.assertEqual(inputs["image"], ["1", 0])
        self.assertEqual(validate_ui_graph(workflow), [])


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def workflow_files():
    """Return sorted paths of the legacy fixture workflows plus the demo workflow. No units apply."""
    legacy = os.path.join(ROOT, "tests", "fixtures", "legacy_workflows")
    files = [os.path.join(legacy, n) for n in os.listdir(legacy) if n.endswith(".json")]
    files.append(os.path.join(ROOT, "workflows", "open_optics_demo.json"))
    return sorted(files)


def load_errors(path):
    """Load the workflow JSON at `path` and return its list of validation error strings."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "nodes" in data:
        return validate_ui_graph(data)
    return validate_api_graph(data)


class WorkflowFilesValidTest(unittest.TestCase):
    def test_all_workflows_validate(self):
        files = workflow_files()
        self.assertGreaterEqual(len(files), 5)
        for path in files:
            with self.subTest(file=os.path.basename(path)):
                errors = load_errors(path)
                self.assertEqual([], errors, "; ".join(map(str, errors)))


class ValidatorCatchesProblemsTest(unittest.TestCase):
    def setUp(self):
        path = os.path.join(ROOT, "tests", "fixtures", "legacy_workflows", "pipeline_depth_api.json")
        with open(path, encoding="utf-8") as f:
            self.graph = copy.deepcopy(json.load(f))

    def test_missing_required_input_fails(self):
        del self.graph["120"]["inputs"]["near_m"]
        errors = validate_api_graph(self.graph)
        self.assertTrue(any("Required input is missing" in e and "120" in e and "near_m" in e
                            for e in errors), errors)

    def test_out_of_range_fails(self):
        self.graph["121"]["inputs"]["strength"] = 5.0
        errors = validate_api_graph(self.graph)
        self.assertTrue(any("strength" in e and "5.0" in e for e in errors), errors)

    def test_unknown_choice_fails(self):
        graph = {
            "1": {"class_type": "LoadImage", "inputs": {"image": "x.png"}},
            "2": {"class_type": "OpenOptics_Anamorphic",
                  "inputs": {"image": ["1", 0], "squeeze": 1.33, "mode": "sideways",
                             "keep_width": False}},
        }
        errors = validate_api_graph(graph)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("mode", errors[0])
        self.assertIn("sideways", errors[0])

    def test_wrong_boolean_kind_fails(self):
        self.graph["120"]["inputs"]["inverse_depth"] = 1.0
        errors = validate_api_graph(self.graph)
        self.assertTrue(any("inverse_depth" in e for e in errors), errors)


class UiValidatorCatchesProblemsTest(unittest.TestCase):
    def setUp(self):
        path = os.path.join(ROOT, "workflows", "open_optics_demo.json")
        with open(path, encoding="utf-8") as f:
            self.workflow = copy.deepcopy(json.load(f))

    def node(self, node_type):
        return next(n for n in self.workflow["nodes"] if n["type"] == node_type)

    def test_ui_missing_required_widget_fails(self):
        self.node("OpenOptics_FocalCrop")["widgets_values"] = [24.0]
        errors = validate_ui_graph(self.workflow)
        self.assertTrue(any("Required input is missing" in e and "target_focal_mm" in e
                            for e in errors), errors)

    def test_ui_out_of_range_fails(self):
        self.node("OpenOptics_Vignette")["widgets_values"][0] = -1.0
        errors = validate_ui_graph(self.workflow)
        self.assertTrue(any("focal_mm" in e for e in errors), errors)

    def test_ui_unknown_choice_fails(self):
        self.node("OpenOptics_Anamorphic")["widgets_values"][1] = "sideways"
        errors = validate_ui_graph(self.workflow)
        self.assertTrue(any("mode" in e and "sideways" in e for e in errors), errors)

    def test_ui_missing_link_fails(self):
        slot = self.node("OpenOptics_Vignette")["inputs"][0]
        self.assertEqual(slot["name"], "image")
        slot["link"] = None
        errors = validate_ui_graph(self.workflow)
        self.assertTrue(any("Required input is missing" in e and "image" in e
                            for e in errors), errors)


def output_problems(node_id, cls_name, outputs, nodes):
    """Return a list of strings, one per wrong tensor in a node's `outputs` tuple.

    `nodes` maps class names to node classes whose RETURN_TYPES say which outputs are
    IMAGE or MASK. Wrong means: dtype not float32, IMAGE not [B, H, W, 3 or 4], MASK not
    3-D, values outside 0..1, or NaN/inf. Values are unitless.
    """
    types = getattr(nodes[cls_name], "RETURN_TYPES", ())
    problems = []
    for i, out in enumerate(outputs):
        if not torch.is_tensor(out):
            continue
        kind = types[i] if i < len(types) else None
        why = []
        if out.dtype != torch.float32:
            why.append(f"dtype {out.dtype} is not float32")
        if kind == "IMAGE" and not (out.dim() == 4 and out.shape[-1] in (3, 4)):
            why.append(f"IMAGE shape {tuple(out.shape)} is not [B, H, W, 3 or 4]")
        if kind == "MASK" and out.dim() != 3:
            why.append(f"MASK shape {tuple(out.shape)} is not 3-D")
        if out.numel() and out.is_floating_point():
            if not bool(torch.isfinite(out).all()):
                why.append("contains NaN or inf")
            elif bool((out < 0).any()) or bool((out > 1).any()):
                why.append("values outside 0..1")
        for w in why:
            problems.append(f"node {node_id} ({cls_name}) output {i}: {w}")
    return problems


class OutputProblemsTest(unittest.TestCase):
    class _Fake:
        RETURN_TYPES = ("IMAGE",)

    def test_output_problems_reports_bad_tensors(self):
        nodes = {"Fake": self._Fake}
        nan = torch.full((1, 4, 4, 3), float("nan"))
        big = torch.full((1, 4, 4, 3), 2.0)
        good = torch.full((1, 4, 4, 3), 0.5, dtype=torch.float32)
        self.assertTrue(output_problems("7", "Fake", (nan,), nodes))
        bad = output_problems("7", "Fake", (big,), nodes)
        self.assertTrue(bad)
        self.assertIn("7", bad[0])
        self.assertIn("Fake", bad[0])
        self.assertEqual(output_problems("7", "Fake", (good,), nodes), [])


def run_api_graph(graph, nodes=None, size=32, frames=3):
    """Run the Open Optics nodes of an API-format graph and return {node_id: output tuple}.

    `nodes` maps class_type to node class (default NODE_CLASS_MAPPINGS). Nodes run in
    dependency order with exactly the workflow's inputs. A link to another Open Optics
    node uses that node's output at the slot; a link to any other node becomes a
    synthetic tensor from the declared type: IMAGE is float32 [frames, size, size, 3]
    random in 0..1 (seeded), MASK is float32 [frames, size, size], a smooth 0..1 ramp.
    Other nodes are never executed. Sizes are in pixels.
    """
    nodes = NODE_CLASS_MAPPINGS if nodes is None else nodes
    results = {}

    def synthetic(typ):
        if typ == "IMAGE":
            torch.manual_seed(0)
            return torch.rand(frames, size, size, 3, dtype=torch.float32)
        if typ == "MASK":
            ramp = torch.linspace(0.0, 1.0, size, dtype=torch.float32)
            return ramp.view(1, size, 1).expand(frames, size, size).contiguous()
        raise ValueError(f"cannot synthesize a link of type {typ}")

    def run(node_id, active):
        if node_id in results:
            return
        if node_id in active:
            raise ValueError(f"cycle at node {node_id}")
        active.add(node_id)
        entry = graph[node_id]
        cls = nodes[entry["class_type"]]
        spec = cls.INPUT_TYPES()
        declared = {**spec.get("required", {}), **spec.get("optional", {})}
        kwargs = {}
        for name, value in entry.get("inputs", {}).items():
            if _is_link(value):
                src = graph.get(value[0])
                if src is not None and src.get("class_type") in nodes:
                    run(value[0], active)
                    kwargs[name] = results[value[0]][value[1]]
                else:
                    kwargs[name] = synthetic(declared[name][0])
            else:
                kwargs[name] = value
        results[node_id] = getattr(cls(), cls.FUNCTION)(**kwargs)
        active.discard(node_id)

    for node_id, entry in graph.items():
        if entry.get("class_type") in nodes:
            run(node_id, set())
    return results


class RunApiGraphTest(unittest.TestCase):
    def test_load_image_to_vignette(self):
        graph = {
            "1": {"class_type": "LoadImage", "inputs": {"image": "a.png"}},
            "2": {"class_type": "OpenOptics_Vignette",
                  "inputs": {"image": ["1", 0], "focal_mm": 35.0, "sensor_width_mm": 36.0,
                             "strength": 0.5, "colorspace": "srgb"}},
        }
        results = run_api_graph(graph)
        self.assertEqual(list(results), ["2"])
        out = results["2"][0]
        self.assertTrue(torch.is_tensor(out))
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(list(out.shape), [3, 32, 32, 3])


def workflow_graph(path):
    """Load the workflow JSON at `path` and return it as an API-format graph dict."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "nodes" in data:
        return ui_to_api(data)
    return data


def legacy_node_problems(nodes):
    """Return a list of strings, one per workflow node of an OpenOptics_ class missing from `nodes`.

    Checks every file of workflow_files(). No units apply.
    """
    problems = []
    for path in workflow_files():
        name = os.path.basename(path)
        for node_id, node in workflow_graph(path).items():
            class_type = node["class_type"]
            if class_type.startswith("OpenOptics_") and class_type not in nodes:
                problems.append(
                    f"{name}: node {node_id} uses unregistered node {class_type}; "
                    "restore it in NODE_CLASS_MAPPINGS")
    return problems


class LegacyNodeProblemsTest(unittest.TestCase):
    def test_legacy_nodes_registered(self):
        self.assertEqual(legacy_node_problems(NODE_CLASS_MAPPINGS), [])

    def test_unregistered_legacy_node_is_reported(self):
        problems = legacy_node_problems({})
        self.assertTrue(any("OpenOptics_" in p for p in problems), problems)


class NodeSetTest(unittest.TestCase):
    KEY = "OpenOptics_Vignette"

    def test_node_set_matches_fixture(self):
        with open(FIXTURE, encoding="utf-8") as f:
            fixture = json.load(f)
        self.assertEqual(node_set_problems(fixture, NODE_CLASS_MAPPINGS), [])
        self.assertEqual(legacy_node_problems(NODE_CLASS_MAPPINGS), [])

    def test_removed_node_is_reported_by_both(self):
        with open(FIXTURE, encoding="utf-8") as f:
            fixture = json.load(f)
        nodes = dict(NODE_CLASS_MAPPINGS)
        del nodes[self.KEY]
        for problems in (node_set_problems(fixture, nodes), legacy_node_problems(nodes)):
            self.assertTrue(any(self.KEY in p for p in problems), problems)


class WorkflowRunTest(unittest.TestCase):
    def test_all_workflows_run(self):
        devices = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])
        for path in workflow_files():
            name = os.path.basename(path)
            for device in devices:
                with self.subTest(file=name, device=device):
                    previous = os.environ.get("OPEN_OPTICS_DEVICE")
                    os.environ["OPEN_OPTICS_DEVICE"] = device
                    try:
                        graph = workflow_graph(path)
                        results = run_api_graph(graph)
                    finally:
                        if previous is None:
                            os.environ.pop("OPEN_OPTICS_DEVICE", None)
                        else:
                            os.environ["OPEN_OPTICS_DEVICE"] = previous
                        if device == "cuda":
                            torch.cuda.empty_cache()
                    self.assertTrue(results, f"{name}: no Open Optics node ran")
                    for node_id, outputs in results.items():
                        cls_name = graph[node_id]["class_type"]
                        problems = output_problems(node_id, cls_name, outputs, NODE_CLASS_MAPPINGS)
                        if cls_name in ("OpenOptics_DepthToMetric", "OpenOptics_DepthTemporalSmooth"):
                            # output 0 is depth in metres, so it may exceed 1
                            problems = [p for p in problems
                                        if not p.endswith("output 0: values outside 0..1")]
                        self.assertEqual([], problems,
                                         f"{name} node {node_id} ({cls_name}): " + "; ".join(problems))


DEMO_CLASSES = {"OpenOptics_" + n for n in (
    "DepthToMetric", "FocalCrop", "DepthOfField", "LensDistortion",
    "Vignette", "ChromaticAberration", "Anamorphic")}


class DemoWorkflowRunTest(unittest.TestCase):
    def check_runs(self, path):
        graph = workflow_graph(path)
        self.assertEqual([], validate_api_graph(graph))
        previous = os.environ.get("OPEN_OPTICS_DEVICE")
        os.environ["OPEN_OPTICS_DEVICE"] = "cpu"
        try:
            results = run_api_graph(graph)
        finally:
            if previous is None:
                os.environ.pop("OPEN_OPTICS_DEVICE", None)
            else:
                os.environ["OPEN_OPTICS_DEVICE"] = previous
        ours = {nid: e["class_type"] for nid, e in graph.items()
                if e.get("class_type") in NODE_CLASS_MAPPINGS}
        self.assertTrue(DEMO_CLASSES <= set(ours.values()))
        for node_id, cls_name in ours.items():
            self.assertIn(node_id, results, f"node {node_id} ({cls_name}) produced no output")
            self.assertTrue(results[node_id], f"node {node_id} ({cls_name}) returned nothing")
            problems = output_problems(node_id, cls_name, results[node_id], NODE_CLASS_MAPPINGS)
            if cls_name == "OpenOptics_DepthToMetric":
                # output 0 is depth in metres, so it may exceed 1
                problems = [p for p in problems if not p.endswith("output 0: values outside 0..1")]
            self.assertEqual([], problems, f"node {node_id} ({cls_name}): " + "; ".join(problems))

    def test_demo_workflow_runs_unchanged(self):
        self.check_runs(os.path.join(ROOT, "workflows", "open_optics_demo.json"))

    def test_released_ui_demo_runs_unchanged(self):
        self.check_runs(os.path.join(ROOT, "tests", "fixtures", "legacy_workflows",
                                     "open_optics_demo_release_ui.json"))

    def test_demo_fails_when_required_input_added(self):
        demo = os.path.join(ROOT, "workflows", "open_optics_demo.json")
        graph = workflow_graph(demo)
        used = sorted({e["class_type"] for e in graph.values()
                       if e.get("class_type") in NODE_CLASS_MAPPINGS})
        self.assertTrue(used)
        for cls_name in used:
            with self.subTest(cls=cls_name):
                base = NODE_CLASS_MAPPINGS[cls_name]

                class Changed(base):
                    @classmethod
                    def INPUT_TYPES(cls):
                        spec = copy.deepcopy(super().INPUT_TYPES())
                        spec.setdefault("required", {})["new_required"] = ("INT", {"default": 1})
                        return spec

                nodes = dict(NODE_CLASS_MAPPINGS)
                nodes[cls_name] = Changed
                errors = validate_api_graph(graph, nodes)
                self.assertTrue(errors)
                self.assertTrue(
                    any("Required input is missing" in m and "new_required" in m for m in errors),
                    errors)


def first_release_kwargs(expected, size=32, frames=3):
    """Return a kwargs dict for one node from fixture entry `expected` (size in pixels).

    Covers every first-release required and optional input: opts['default'] when present,
    else the first choice for combos. IMAGE is a seeded float32 random [frames, size, size, 3]
    in 0..1, MASK a float32 ramp [frames, size, size], and any input named '*depth*' a
    float32 [frames, size, size] tensor in 0.5..1. Other types without a default get
    False, the minimum or 0.
    """
    torch.manual_seed(0)
    kwargs = {}
    for section in ("required", "optional"):
        for name, typ, opts in expected.get(section, []):
            if "depth" in name and typ in ("IMAGE", "MASK"):
                kwargs[name] = 0.5 + 0.5 * torch.rand(frames, size, size, dtype=torch.float32)
            elif typ == "IMAGE":
                kwargs[name] = torch.rand(frames, size, size, 3, dtype=torch.float32)
            elif typ == "MASK":
                ramp = torch.linspace(0.0, 1.0, size, dtype=torch.float32)
                kwargs[name] = ramp.view(1, size, 1).expand(frames, size, size).contiguous()
            elif "default" in opts:
                kwargs[name] = opts["default"]
            elif isinstance(typ, list):
                kwargs[name] = typ[0]
            elif typ == "BOOLEAN":
                kwargs[name] = False
            elif typ == "STRING":
                kwargs[name] = ""
            else:
                kwargs[name] = opts.get("min", 0)
    return kwargs


class FirstReleaseKwargsTest(unittest.TestCase):
    def test_kwargs_keys_and_shapes(self):
        with open(FIXTURE, encoding="utf-8") as f:
            fixture = json.load(f)
        for key, expected in fixture.items():
            with self.subTest(key=key):
                kwargs = first_release_kwargs(expected)
                names = [e[0] for s in ("required", "optional") for e in expected.get(s, [])]
                self.assertEqual(set(kwargs), set(names))
                for s in ("required", "optional"):
                    for name, typ, _ in expected.get(s, []):
                        if typ == "IMAGE" and "depth" not in name:
                            self.assertEqual(list(kwargs[name].shape), [3, 32, 32, 3])
                            self.assertEqual(kwargs[name].dtype, torch.float32)


def run_first_release(key, device, extra=None):
    """Run node `key` on `device` ('cpu' or 'cuda') with first-release inputs.

    Sets OPEN_OPTICS_DEVICE to `device` for the call and restores it afterwards.
    `extra` is an optional dict of further keyword inputs passed to the node as well.
    Returns (kwargs, outputs): the kwargs dict used and the node's output tuple.
    """
    with open(FIXTURE, encoding="utf-8") as f:
        expected = json.load(f)[key]
    kwargs = first_release_kwargs(expected)
    kwargs.update(extra or {})
    if "depth_mask" in kwargs and "depth_image" in kwargs:
        del kwargs["depth_image"]  # nodes accept exactly one depth source
    cls = NODE_CLASS_MAPPINGS[key]
    previous = os.environ.get("OPEN_OPTICS_DEVICE")
    os.environ["OPEN_OPTICS_DEVICE"] = device
    try:
        outputs = getattr(cls(), cls.FUNCTION)(**kwargs)
    finally:
        if previous is None:
            os.environ.pop("OPEN_OPTICS_DEVICE", None)
        else:
            os.environ["OPEN_OPTICS_DEVICE"] = previous
    return kwargs, outputs


class RunFirstReleaseTest(unittest.TestCase):
    def test_returns_tuple_on_cpu(self):
        _, outputs = run_first_release("OpenOptics_DepthToMetric", "cpu")
        self.assertIsInstance(outputs, tuple)

    def test_env_restored(self):
        before = os.environ.get("OPEN_OPTICS_DEVICE")
        run_first_release("OpenOptics_DepthToMetric", "cpu")
        self.assertEqual(os.environ.get("OPEN_OPTICS_DEVICE"), before)


class FirstReleaseCallTest(unittest.TestCase):
    def test_every_node_runs_with_first_release_inputs(self):
        with open(FIXTURE, encoding="utf-8") as f:
            fixture = json.load(f)
        devices = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])
        for key, expected in fixture.items():
            for device in devices:
                with self.subTest(key=key, device=device):
                    try:
                        kwargs, outputs = run_first_release(key, device)
                    finally:
                        if device == "cuda":
                            torch.cuda.empty_cache()
                    self.assertIsInstance(outputs, tuple)
                    self.assertGreaterEqual(len(outputs), len(expected["return_types"]))
                    problems = output_problems("0", key, outputs, NODE_CLASS_MAPPINGS)
                    if key in ("OpenOptics_DepthToMetric", "OpenOptics_DepthTemporalSmooth"):
                        # output 0 is depth in metres, so it may exceed 1
                        problems = [p for p in problems
                                    if not p.endswith("output 0: values outside 0..1")]
                    self.assertEqual([], problems, "; ".join(problems))
                    types = NODE_CLASS_MAPPINGS[key].RETURN_TYPES
                    ref = next((v for v in kwargs.values()
                                if torch.is_tensor(v) and v.dim() == 4), None)
                    for i, out in enumerate(outputs):
                        if i < len(types) and types[i] == "IMAGE" and ref is not None:
                            # Anamorphic resizes the width by design: check the batch only
                            n = 1 if key == "OpenOptics_Anamorphic" else 3
                            self.assertEqual(tuple(out.shape[:n]), tuple(ref.shape[:n]),
                                             f"output {i} batch/spatial size changed")


    def test_explicit_defaults_equal_omitted_inputs(self):
        with open(FIXTURE, encoding="utf-8") as f:
            fixture = json.load(f)
        for key, expected in fixture.items():
            with self.subTest(key=key):
                cls = NODE_CLASS_MAPPINGS[key]
                old = {e[0] for s in ("required", "optional") for e in expected.get(s, [])}
                added = {}
                spec = cls.INPUT_TYPES()
                for section in ("required", "optional"):
                    for name, entry in spec.get(section, {}).items():
                        if name in old:
                            continue
                        typ = entry[0]
                        opts = entry[1] if len(entry) > 1 else {}
                        if "default" in opts:
                            added[name] = opts["default"]
                        elif isinstance(typ, (list, tuple)):
                            added[name] = typ[0]
                _, before = run_first_release(key, "cpu")
                _, after = run_first_release(key, "cpu", added)
                n = min(len(cls.RETURN_TYPES), len(before))
                self.assertGreaterEqual(len(after), n)
                for i in range(n):
                    if torch.is_tensor(before[i]):
                        self.assertTrue(torch.allclose(before[i], after[i], atol=1e-6),
                                        f"output {i} changed with explicit defaults")
                    else:
                        self.assertEqual(before[i], after[i])
                for i in range(n, len(after)):
                    self.assertEqual(len(before), len(after))
                    if torch.is_tensor(before[i]):
                        self.assertTrue(torch.allclose(before[i], after[i], atol=1e-6))
                    else:
                        self.assertEqual(before[i], after[i])
                problems = output_problems("0", key, after, NODE_CLASS_MAPPINGS)
                if key in ("OpenOptics_DepthToMetric", "OpenOptics_DepthTemporalSmooth"):
                    problems = [p for p in problems
                                if not p.endswith("output 0: values outside 0..1")]
                self.assertEqual([], problems, "; ".join(problems))


class FixturesPresentTest(unittest.TestCase):
    def test_legacy_files_and_input_keys(self):
        legacy = os.path.join(ROOT, "tests", "fixtures", "legacy_workflows")
        expected = {n + ".json" for n in (
            "pipeline_depth_api", "pipeline_dof_api", "pipeline_full_api",
            "open_optics_demo_release_ui")}
        self.assertEqual(expected, set(os.listdir(legacy)))
        with open(FIXTURE, encoding="utf-8") as f:
            recorded = json.load(f)
        self.assertEqual(set(NODE_CLASS_MAPPINGS), set(recorded))


class ClaudeMdRuleTest(unittest.TestCase):
    def test_claude_md_has_compat_rule(self):
        with open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8") as f:
            lines = f.read().splitlines()
        needed = ("optional", "tests/fixtures/legacy_workflows/",
                  "first_release_inputs.json", "Never edit")
        self.assertTrue(
            any(all(n in line for n in needed) for line in lines),
            "CLAUDE.md lacks the workflow compatibility line")


if __name__ == "__main__":
    unittest.main()
