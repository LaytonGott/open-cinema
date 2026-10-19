"""Saved workflows store widget values by position, so first-release inputs must not change."""
import copy
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


if __name__ == "__main__":
    unittest.main()
