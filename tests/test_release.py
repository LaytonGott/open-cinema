"""Release checks. The ComfyUI import scan matches docs/licence-scan.md.

ComfyUI is GPL-3.0, so the only place this repository may import it is the guarded, optional
`import comfy.model_management` in open_optics_nodes/device.py. The scan reads every import
statement (also inside functions) in the root __init__.py, open_optics/ and open_optics_nodes/.
"""
import ast
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
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            else:
                continue
            hits.extend((rel, m) for m in modules if m.split(".")[0] in COMFY_ROOTS)
    return sorted(hits)


class TestComfyImportScan(unittest.TestCase):
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
        hits = scan_comfy_imports()
        if hits:
            self.assertTrue(
                _is_gpl3(_licence_text()),
                f"ComfyUI is imported ({hits}) so LICENSE must be GPL-3.0, but LICENSE is not",
            )


def _readme_text():
    path = ROOT / "README.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


class TestReadme(unittest.TestCase):
    def test_readme_exists(self):
        self.assertTrue((ROOT / "README.md").is_file(), "README.md is missing at the repo root")

    def test_readme_has_headings(self):
        headings = [line for line in _readme_text().splitlines() if line.startswith("#")]
        for name in ("Install", "Nodes", "Example workflow", "Tests", "Licence"):
            self.assertTrue(
                any(name.lower() in h.lower() for h in headings),
                f"README.md has no heading containing '{name}'",
            )

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


class TestWorkflowLinks(unittest.TestCase):
    def test_link_types_match(self):
        wf = _load_workflow()
        nodes = {n["id"]: n for n in wf["nodes"]}
        for link in wf["links"]:
            _lid, from_node, from_slot, to_node, to_slot, link_type = link
            out_type = nodes[from_node]["outputs"][from_slot]["type"]
            in_type = nodes[to_node]["inputs"][to_slot]["type"]
            self.assertEqual(out_type, link_type,
                             f"link {link}: source output type is {out_type}, link type is {link_type}")
            self.assertEqual(in_type, link_type,
                             f"link {link}: target input type is {in_type}, link type is {link_type}")

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
        wf = _load_workflow()
        for node in wf["nodes"]:
            if not node["type"].startswith("OpenOptics_"):
                continue
            expected = len(widget_inputs(NODE_CLASS_MAPPINGS[node["type"]]))
            actual = len(node.get("widgets_values", []))
            self.assertEqual(actual, expected,
                             f"{node['type']}: widgets_values has {actual} values, node has {expected} widget inputs")

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


class TestWidgetValues(unittest.TestCase):
    def test_widget_values_valid(self):
        wf = _load_workflow()
        for node in wf["nodes"]:
            if not node["type"].startswith("OpenOptics_"):
                continue
            pairs = widget_inputs(NODE_CLASS_MAPPINGS[node["type"]])
            for (name, spec), value in zip(pairs, node.get("widgets_values", [])):
                kind = spec[0]
                where = f"{node['type']} input {name} value {value!r}"
                opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                if isinstance(kind, (list, tuple)):
                    self.assertIn(value, list(kind), f"{where} is not in choices {list(kind)}")
                    continue
                if kind == "BOOLEAN":
                    self.assertIsInstance(value, bool, f"{where} is not a bool")
                elif kind == "STRING":
                    self.assertIsInstance(value, str, f"{where} is not a str")
                else:
                    ok = isinstance(value, int) if kind == "INT" else isinstance(value, (int, float))
                    self.assertTrue(ok and not isinstance(value, bool), f"{where} is not a valid {kind}")
                    if "min" in opts:
                        self.assertGreaterEqual(value, opts["min"], f"{where} is below min {opts['min']}")
                    if "max" in opts:
                        self.assertLessEqual(value, opts["max"], f"{where} is above max {opts['max']}")


if __name__ == "__main__":
    unittest.main()
