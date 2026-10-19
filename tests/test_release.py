"""Release checks. The ComfyUI import scan matches docs/licence-scan.md.

ComfyUI is GPL-3.0, so the only place this repository may import it is the guarded, optional
`import comfy.model_management` in open_optics_nodes/device.py. The scan reads every import
statement (also inside functions) in the root __init__.py, open_optics/ and open_optics_nodes/.
"""
import ast
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
