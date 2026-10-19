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


if __name__ == "__main__":
    unittest.main()
