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


if __name__ == "__main__":
    unittest.main()
