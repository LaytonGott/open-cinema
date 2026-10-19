"""Release checks. The ComfyUI import scan matches docs/licence-scan.md.

ComfyUI is GPL-3.0, so the only place this repository may import it is the guarded, optional
`import comfy.model_management` in open_optics_nodes/device.py. The scan reads every import
statement (also inside functions) in the root __init__.py, open_optics/ and open_optics_nodes/.
"""
import ast
import copy
import json
import unittest
from pathlib import Path

from open_optics_nodes import NODE_CLASS_MAPPINGS

ROOT = Path(__file__).resolve().parent.parent

COMFY_ROOTS = {
    "comfy", "comfy_api", "comfy_extras", "comfy_execution", "folder_paths",
    "nodes", "server", "execution", "latent_preview", "node_helpers",
}

ALLOWED_FILES = {"open_optics_nodes/device.py"}


def scan_comfy_imports():
    """Return a sorted list of (path relative to the repo root, module) for ComfyUI imports."""
    files = [ROOT / "__init__.py"]
    files += sorted((ROOT / "open_optics").rglob("*.py"))
    files += sorted((ROOT / "open_optics_nodes").rglob("*.py"))
    hits = []
    for path in files:
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        hits.extend((rel, m) for m in comfy_imports_in_source(path.read_text(encoding="utf-8")))
    return sorted(hits)


def comfy_imports_in_source(source):
    """Return the list of ComfyUI module names imported anywhere in the Python source string."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules = [node.module]
        else:
            continue
        found.extend(m for m in modules if m.split(".")[0] in COMFY_ROOTS)
    return found


class TestComfyImportScan(unittest.TestCase):
    def test_source_scan_detects_lazy_and_guarded(self):
        lazy = "def f():\n    import comfy.utils\n"
        guarded = "try:\n    from folder_paths import x\nexcept ImportError:\n    x = None\n"
        self.assertEqual(comfy_imports_in_source(lazy), ["comfy.utils"])
        self.assertEqual(comfy_imports_in_source(guarded), ["folder_paths"])
        self.assertEqual(comfy_imports_in_source("import math\n"), [])

    def test_scan_finds_device_helper_import(self):
        hits = scan_comfy_imports()
        self.assertIn(("open_optics_nodes/device.py", "comfy.model_management"), hits, f"hits: {hits}")

    def test_scan_only_allowed_files(self):
        hits = scan_comfy_imports()
        bad = [h for h in hits if h[0] not in ALLOWED_FILES]
        self.assertEqual(bad, [], f"ComfyUI imports outside {sorted(ALLOWED_FILES)}: {hits}")


def _licence_text():
    path = ROOT / "LICENSE"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _is_gpl3(text):
    return "GNU GENERAL PUBLIC LICENSE" in text and "Version 3, 29 June 2007" in text


class TestLicenceFile(unittest.TestCase):
    def test_license_exists(self):
        self.assertTrue((ROOT / "LICENSE").is_file(), "LICENSE is missing at the repo root")

    def test_license_is_gpl3(self):
        text = _licence_text()
        self.assertIn("GNU GENERAL PUBLIC LICENSE", text)
        self.assertIn("Version 3, 29 June 2007", text)

    def test_gpl_when_comfy_imported(self):
        problem = licence_problem(scan_comfy_imports(), _licence_text())
        self.assertIsNone(problem, problem)


def licence_problem(hits, licence_text):
    """Return a message when hits is non-empty and licence_text is not GPL-3.0, else None."""
    if hits and not _is_gpl3(licence_text):
        return f"ComfyUI is imported ({hits}) so LICENSE must be GPL-3.0, but LICENSE is not"
    return None


class TestLicenceRule(unittest.TestCase):
    MIT = "MIT License\n\nPermission is hereby granted, free of charge, to any person..."

    def test_mit_with_comfy_import_is_a_problem(self):
        self.assertIsNotNone(licence_problem([("x.py", "comfy")], self.MIT))

    def test_gpl_with_comfy_import_is_fine(self):
        self.assertIsNone(licence_problem([("x.py", "comfy")], _licence_text()))

    def test_mit_without_comfy_import_is_fine(self):
        self.assertIsNone(licence_problem([], self.MIT))

    def test_real_license_is_gpl3(self):
        text = _licence_text()
        self.assertTrue(text.strip())
        self.assertTrue(_is_gpl3(text))


def _readme_text():
    path = ROOT / "README.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def readme_problems(text, display_names):
    """Return a list of messages for missing README headings and unmentioned node display names."""
    problems = []
    headings = [line for line in text.splitlines() if line.startswith("#")]
    for name in ("Install", "Nodes", "Example workflow", "Tests", "Licence"):
        if not any(name.lower() in h.lower() for h in headings):
            problems.append(f"README.md has no heading containing '{name}'")
    for name in display_names:
        if name not in text:
            problems.append(f"README.md does not mention node '{name}'")
    return problems


class TestReadme(unittest.TestCase):
    def test_readme_exists(self):
        self.assertTrue((ROOT / "README.md").is_file(), "README.md is missing at the repo root")

    def test_readme_has_headings(self):
        from open_optics_nodes import NODE_DISPLAY_NAME_MAPPINGS

        self.assertEqual(readme_problems(_readme_text(), list(NODE_DISPLAY_NAME_MAPPINGS.values())), [])

    def test_readme_problems_detect_breakage(self):
        from open_optics_nodes import NODE_DISPLAY_NAME_MAPPINGS

        names = list(NODE_DISPLAY_NAME_MAPPINGS.values())
        text = "\n".join(l for l in _readme_text().splitlines() if l.strip() != "## Tests")
        broken = text.replace(names[0], "")
        problems = readme_problems(broken, names)
        self.assertIn("README.md has no heading containing 'Tests'", problems)
        self.assertIn(f"README.md does not mention node '{names[0]}'", problems)

    def test_readme_intro_mentions_comfyui(self):
        intro = _readme_text().split("\n## ")[0]
        self.assertIn("ComfyUI", intro, "README.md intro (before the first '##' heading) does not mention ComfyUI")


def _readme_section(keyword):
    """Return the text of the README section whose '#' heading contains keyword (case-insensitive).

    The section runs from the line after the heading to the next heading of the same or higher
    level, or to the end of the file. Returns "" when no heading matches.
    """
    lines = _readme_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("#") and keyword.lower() in line.lower():
            level = len(line) - len(line.lstrip("#"))
            body = []
            for later in lines[i + 1:]:
                if later.startswith("#") and len(later) - len(later.lstrip("#")) <= level:
                    break
                body.append(later)
            return "\n".join(body)
    return ""


class TestReadmeInstall(unittest.TestCase):
    def test_install_section_content(self):
        section = _readme_section("Install")
        self.assertTrue(section, "README.md has no Install section")
        for needle in ("ComfyUI\\custom_nodes\\open-optics", "git clone", "restart", "pip", "Open Optics"):
            self.assertIn(needle.lower(), section.lower(), f"README.md Install section does not mention '{needle}'")


class TestReadmeTests(unittest.TestCase):
    def test_tests_section_content(self):
        section = _readme_section("Tests")
        self.assertTrue(section, "README.md has no Tests section")
        for needle in ("npm test", "npm run test:bench", "venv", "CUDA"):
            self.assertIn(needle.lower(), section.lower(), f"README.md Tests section does not mention '{needle}'")


class TestReadmeDevice(unittest.TestCase):
    def test_readme_device_behaviour(self):
        text = _readme_text()
        lower = text.lower()
        for needle in ("OPEN_OPTICS_DEVICE", "cpu", "cuda", "auto", "chunk_frames"):
            self.assertIn(needle.lower(), lower, f"README.md does not mention '{needle}'")
        self.assertTrue(
            "fall back" in lower or "falls back" in lower,
            "README.md does not mention 'fall back' or 'falls back'",
        )


class TestReadmeNodes(unittest.TestCase):
    def test_nodes_table_matches_registry(self):
        from open_optics_nodes import NODE_DISPLAY_NAME_MAPPINGS

        section = _readme_section("Nodes")
        self.assertTrue(section, "README.md has no Nodes section")
        rows = [
            line for line in section.splitlines()
            if line.strip().startswith("|") and "OpenOptics_" in line
        ]
        self.assertEqual(len(rows), len(NODE_CLASS_MAPPINGS), "README Nodes table row count differs from registry")
        for key in NODE_CLASS_MAPPINGS:
            name = NODE_DISPLAY_NAME_MAPPINGS[key]
            self.assertTrue(
                any(key in row and name in row for row in rows),
                f"README Nodes table has no row with '{key}' and '{name}'",
            )


class TestReadmeLicence(unittest.TestCase):
    def test_licence_section_names_licence(self):
        section = _readme_section("Licence")
        self.assertTrue(section, "README.md has no Licence section")
        self.assertIn("GPL-3.0", section, "README.md Licence section does not name 'GPL-3.0'")
        self.assertTrue(_is_gpl3(_licence_text()), "LICENSE file is not GPL-3.0")

    def test_licence_section_states_scan(self):
        section = _readme_section("Licence")
        self.assertTrue(section, "README.md has no Licence section")
        for needle in ("comfy.model_management", "combined work", "get_device", "device.py"):
            self.assertIn(needle.lower(), section.lower(), f"README.md Licence section does not mention '{needle}'")

    def test_licence_section_states_dependencies(self):
        section = _readme_section("Licence")
        self.assertTrue(section, "README.md has no Licence section")
        for needle in ("no code was copied", "torch", "numpy", "not bundled"):
            self.assertIn(needle.lower(), section.lower(), f"README.md Licence section does not mention '{needle}'")


class TestReadmeWorkflowSection(unittest.TestCase):
    def test_example_workflow_section_content(self):
        from open_optics_nodes import NODE_DISPLAY_NAME_MAPPINGS

        section = _readme_section("Example workflow")
        self.assertTrue(section.strip(), "README.md has no Example workflow section")
        self.assertNotEqual(section.strip(), "TODO", "README.md Example workflow section is 'TODO'")
        stages = ("DepthToMetric", "FocalCrop", "DepthOfField", "LensDistortion",
                  "Vignette", "ChromaticAberration", "Anamorphic")
        needles = ["workflows/open_optics_demo.json", "input", "depth map", "Depth Anything"]
        needles += [NODE_DISPLAY_NAME_MAPPINGS[f"OpenOptics_{s}"] for s in stages]
        needles.append("Preview")
        for needle in needles:
            self.assertIn(needle.lower(), section.lower(), f"README.md Example workflow section does not mention '{needle}'")


def _load_workflow():
    path = ROOT / "workflows" / "open_optics_demo.json"
    return json.loads(path.read_text(encoding="utf-8"))


class TestWorkflowFile(unittest.TestCase):
    def test_workflow_valid_json(self):
        wf = _load_workflow()
        for key in ("nodes", "links", "version"):
            self.assertIn(key, wf, f"workflow has no key '{key}'")

    def test_workflow_links_well_formed(self):
        wf = _load_workflow()
        node_ids = {n["id"] for n in wf["nodes"]}
        seen = set()
        for link in wf["links"]:
            self.assertIsInstance(link, list, f"link {link} is not a list")
            self.assertEqual(len(link), 6, f"link {link} does not have 6 items")
            link_id, from_node, _from_slot, to_node, _to_slot, _type = link
            self.assertNotIn(link_id, seen, f"link id {link_id} is duplicated: {link}")
            seen.add(link_id)
            self.assertIn(from_node, node_ids, f"link {link} starts at missing node {from_node}")
            self.assertIn(to_node, node_ids, f"link {link} ends at missing node {to_node}")

    def test_workflow_node_types_present(self):
        wf = _load_workflow()
        types = [n["type"] for n in wf["nodes"]]
        self.assertEqual(types.count("LoadImage"), 2, f"LoadImage count is {types.count('LoadImage')}, expected 2")
        for name in ("DepthToMetric", "FocalCrop", "DepthOfField", "LensDistortion",
                     "Vignette", "ChromaticAberration", "Anamorphic"):
            self.assertIn(f"OpenOptics_{name}", types, f"workflow has no OpenOptics_{name} node")
        self.assertIn("PreviewImage", types, "workflow has no PreviewImage node")
        allowed = set(NODE_CLASS_MAPPINGS) | {"LoadImage", "PreviewImage", "SaveImage"}
        for t in types:
            self.assertIn(t, allowed, f"node type '{t}' is not an Open Optics node, LoadImage, PreviewImage or SaveImage")

    def test_workflow_node_set_exact(self):
        wf = _load_workflow()
        actual = sorted(n["type"] for n in wf["nodes"])
        expected = sorted([
            "LoadImage", "LoadImage", "OpenOptics_DepthToMetric", "OpenOptics_FocalCrop",
            "OpenOptics_DepthOfField", "OpenOptics_LensDistortion", "OpenOptics_Vignette",
            "OpenOptics_ChromaticAberration", "OpenOptics_Anamorphic", "PreviewImage",
        ])
        self.assertEqual(actual, expected, f"workflow node types are {actual}, expected {expected}")

    def test_workflow_wiring_order(self):
        wf = _load_workflow()
        nodes = {n["id"]: n for n in wf["nodes"]}
        edges = set()
        load_to_depth = set()
        load_to_crop = set()
        for _lid, from_node, from_slot, to_node, to_slot, _t in wf["links"]:
            from_type = nodes[from_node]["type"]
            target = nodes[to_node]
            slot_name = target["inputs"][to_slot]["name"]
            edges.add((from_type, from_slot, target["type"], slot_name))
            if from_type == "LoadImage" and target["type"] == "OpenOptics_DepthToMetric":
                load_to_depth.add(from_node)
            if from_type == "LoadImage" and target["type"] == "OpenOptics_FocalCrop":
                load_to_crop.add(from_node)
        required = [
            ("LoadImage", 0, "OpenOptics_DepthToMetric", "depth_image"),
            ("OpenOptics_DepthToMetric", 0, "OpenOptics_DepthOfField", "depth_mask"),
            ("OpenOptics_FocalCrop", 0, "OpenOptics_DepthOfField", "image"),
            ("OpenOptics_DepthOfField", 0, "OpenOptics_LensDistortion", "image"),
            ("OpenOptics_LensDistortion", 0, "OpenOptics_Vignette", "image"),
            ("OpenOptics_Vignette", 0, "OpenOptics_ChromaticAberration", "image"),
            ("OpenOptics_ChromaticAberration", 0, "OpenOptics_Anamorphic", "image"),
            ("OpenOptics_Anamorphic", 0, "PreviewImage", "images"),
            ("LoadImage", 0, "OpenOptics_FocalCrop", "image"),
        ]
        for edge in required:
            self.assertIn(edge, edges, f"workflow is missing the connection {edge}")
        self.assertEqual(len(load_to_depth), 1, f"LoadImage nodes feeding DepthToMetric: {load_to_depth}")
        self.assertEqual(len(load_to_crop), 1, f"LoadImage nodes feeding FocalCrop: {load_to_crop}")
        self.assertTrue(load_to_depth.isdisjoint(load_to_crop),
                        "the same LoadImage feeds both DepthToMetric and FocalCrop")


def link_type_problems(wf):
    """Return a list of messages, one per link whose type differs from its source output or target input type."""
    problems = []
    nodes = {n["id"]: n for n in wf["nodes"]}
    for link in wf["links"]:
        _lid, from_node, from_slot, to_node, to_slot, link_type = link
        out_type = nodes[from_node]["outputs"][from_slot]["type"]
        in_type = nodes[to_node]["inputs"][to_slot]["type"]
        if out_type != link_type:
            problems.append(f"link {link[0]}: source output type is {out_type}, link type is {link_type}")
        if in_type != link_type:
            problems.append(f"link {link[0]}: target input type is {in_type}, link type is {link_type}")
    return problems


class TestWorkflowLinks(unittest.TestCase):
    def test_link_types_match(self):
        problems = link_type_problems(_load_workflow())
        self.assertEqual(problems, [], f"link type problems: {problems}")

    def test_link_type_problems_detect_breakage(self):
        wf = copy.deepcopy(_load_workflow())
        link = wf["links"][0]
        link[5] = "MASK" if link[5] == "IMAGE" else "IMAGE"
        problems = link_type_problems(wf)
        self.assertTrue(problems, "link_type_problems found nothing in a workflow with a wrong link type")
        self.assertIn(str(link[0]), " ".join(problems))

    def test_node_ids_unique(self):
        wf = _load_workflow()
        ids = [n["id"] for n in wf["nodes"]]
        self.assertEqual(len(ids), len(set(ids)), f"node ids are not unique: {ids}")

    def test_node_link_references(self):
        wf = _load_workflow()
        nodes = {n["id"]: n for n in wf["nodes"]}
        by_id = {link[0]: link for link in wf["links"]}
        for link in wf["links"]:
            lid, from_node, from_slot, to_node, to_slot, _t = link
            out_links = nodes[from_node]["outputs"][from_slot].get("links") or []
            self.assertIn(lid, out_links, f"link {link}: source output links are {out_links}")
            in_link = nodes[to_node]["inputs"][to_slot].get("link")
            self.assertEqual(in_link, lid, f"link {link}: target input link is {in_link}")
        for node in wf["nodes"]:
            for slot, inp in enumerate(node.get("inputs", [])):
                lid = inp.get("link")
                if lid is None:
                    continue
                self.assertIn(lid, by_id, f"node {node['id']} input {slot} references missing link {lid}")
                link = by_id[lid]
                self.assertEqual((link[3], link[4]), (node["id"], slot),
                                 f"node {node['id']} input {slot} references link {link} with another target")
            for slot, out in enumerate(node.get("outputs", [])):
                for lid in out.get("links") or []:
                    self.assertIn(lid, by_id, f"node {node['id']} output {slot} references missing link {lid}")
                    link = by_id[lid]
                    self.assertEqual((link[1], link[2]), (node["id"], slot),
                                     f"node {node['id']} output {slot} references link {link} with another source")


def widget_inputs(cls):
    """Return the (name, spec) pairs of a node class's widget inputs, required first, in order.

    A widget is a list/combo spec, or a spec of type INT, FLOAT, STRING or BOOLEAN.
    """
    spec = cls.INPUT_TYPES()
    pairs = []
    for section in ("required", "optional"):
        for name, value in (spec.get(section) or {}).items():
            kind = value[0]
            if isinstance(kind, (list, tuple)) or kind in ("INT", "FLOAT", "STRING", "BOOLEAN"):
                pairs.append((name, value))
    return pairs


class TestWorkflowWidgets(unittest.TestCase):
    def test_widget_count(self):
        problems = widget_value_problems(_load_workflow())
        self.assertEqual(problems, [], f"widget value problems: {problems}")

    def test_inputs_match_registered(self):
        wf = _load_workflow()
        for node in wf["nodes"]:
            if not node["type"].startswith("OpenOptics_"):
                continue
            spec = NODE_CLASS_MAPPINGS[node["type"]].INPUT_TYPES()
            declared = {**(spec.get("required") or {}), **(spec.get("optional") or {})}
            for inp in node.get("inputs", []):
                name = inp["name"]
                self.assertIn(name, declared, f"{node['type']} input {name} is not in INPUT_TYPES")
                kind = declared[name][0]
                accepted = ["COMBO"] if isinstance(kind, (list, tuple)) else [kind]
                widget = inp.get("widget")
                if widget:
                    accepted.append(widget.get("type", ""))
                    accepted.append(widget.get("name", ""))
                self.assertIn(inp["type"], accepted,
                              f"{node['type']} input {name} type {inp['type']!r} does not match declared {kind!r}")

    def test_outputs_match_return_types(self):
        wf = _load_workflow()
        for node in wf["nodes"]:
            if not node["type"].startswith("OpenOptics_"):
                continue
            cls = NODE_CLASS_MAPPINGS[node["type"]]
            outputs = node.get("outputs", [])
            self.assertEqual(len(outputs), len(cls.RETURN_TYPES),
                             f"{node['type']} (id {node['id']}): {len(outputs)} outputs, RETURN_TYPES has {len(cls.RETURN_TYPES)}")
            names = getattr(cls, "RETURN_NAMES", None)
            for i, out in enumerate(outputs):
                self.assertEqual(out["type"], cls.RETURN_TYPES[i],
                                 f"{node['type']} (id {node['id']}) output {i} type")
                if names:
                    self.assertEqual(out["name"], names[i],
                                     f"{node['type']} (id {node['id']}) output {i} name")


def widget_value_problems(wf):
    """Return a list of messages, one per widget value or widget count that does not fit its node's INPUT_TYPES."""
    problems = []
    for node in wf["nodes"]:
        if not node["type"].startswith("OpenOptics_"):
            continue
        pairs = widget_inputs(NODE_CLASS_MAPPINGS[node["type"]])
        values = node.get("widgets_values", [])
        if len(values) != len(pairs):
            problems.append(f"{node['type']} (id {node['id']}): widgets_values has {len(values)} values, "
                            f"node has {len(pairs)} widget inputs")
        for (name, spec), value in zip(pairs, values):
            kind = spec[0]
            where = f"{node['type']} (id {node['id']}) input {name} value {value!r}"
            opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            if isinstance(kind, (list, tuple)):
                if value not in list(kind):
                    problems.append(f"{where} is not in choices {list(kind)}")
                continue
            if kind == "BOOLEAN":
                if not isinstance(value, bool):
                    problems.append(f"{where} is not a bool")
            elif kind == "STRING":
                if not isinstance(value, str):
                    problems.append(f"{where} is not a str")
            else:
                ok = isinstance(value, int) if kind == "INT" else isinstance(value, (int, float))
                if not ok or isinstance(value, bool):
                    problems.append(f"{where} is not a valid {kind}")
                    continue
                if "min" in opts and value < opts["min"]:
                    problems.append(f"{where} is below min {opts['min']}")
                if "max" in opts and value > opts["max"]:
                    problems.append(f"{where} is above max {opts['max']}")
    return problems


class TestWidgetValues(unittest.TestCase):
    def test_widget_values_valid(self):
        problems = widget_value_problems(_load_workflow())
        self.assertEqual(problems, [], f"widget value problems: {problems}")

    def test_widget_problems_detect_breakage(self):
        wf = copy.deepcopy(_load_workflow())
        nodes = [n for n in wf["nodes"]
                 if n["type"].startswith("OpenOptics_") and n.get("widgets_values")
                 and widget_inputs(NODE_CLASS_MAPPINGS[n["type"]])[0][1][0] != "STRING"]
        self.assertGreaterEqual(len(nodes), 2, "need two OpenOptics nodes with widgets")
        bad_node, short_node = nodes[0], nodes[1]
        bad_node["widgets_values"][0] = "bad"
        short_node["widgets_values"].pop()
        text = "\n".join(widget_value_problems(wf))
        self.assertIn(f"{bad_node['type']} (id {bad_node['id']}) input", text)
        self.assertIn("value 'bad'", text)
        self.assertIn(f"{short_node['type']} (id {short_node['id']}): widgets_values has", text)


class TestFailureMessages(unittest.TestCase):
    def test_readme_message_names_heading_and_file(self):
        text = "\n".join(l for l in _readme_text().splitlines() if "licence" not in l.lower() or not l.startswith("#"))
        message = "\n".join(readme_problems(text, []))
        self.assertIn("Licence", message)
        self.assertIn("README.md", message)

    def test_link_message_names_link_id(self):
        wf = copy.deepcopy(_load_workflow())
        link = wf["links"][0]
        link[5] = "MASK" if link[5] == "IMAGE" else "IMAGE"
        self.assertIn(f"link {link[0]}", "\n".join(link_type_problems(wf)))

    def test_widget_message_names_node_type_and_widget(self):
        wf = copy.deepcopy(_load_workflow())
        for node in wf["nodes"]:
            if not node["type"].startswith("OpenOptics_"):
                continue
            pairs = widget_inputs(NODE_CLASS_MAPPINGS[node["type"]])
            values = node.get("widgets_values", [])
            for i, (name, spec) in enumerate(pairs[:len(values)]):
                opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                if spec[0] in ("INT", "FLOAT") and "max" in opts:
                    values[i] = opts["max"] * 1000 + 1000
                    message = "\n".join(widget_value_problems(wf))
                    self.assertIn(node["type"], message)
                    self.assertIn(name, message)
                    return
        self.fail("no OpenOptics node with a numeric widget that has a max")


if __name__ == "__main__":
    unittest.main()
