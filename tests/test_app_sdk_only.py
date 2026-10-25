import re
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"
FORBIDDEN = re.compile(r"""["'](/prompt|/history|/upload/image|/ws|/view)["'?/]""")


class AppSdkOnlyTest(unittest.TestCase):
    def setUp(self):
        self.files = {p: p.read_text(encoding="utf-8") for p in APP_DIR.rglob("*.py")}
        self.assertTrue(self.files)

    def test_imports_sdk_and_proxy(self):
        text = "\n".join(self.files.values())
        self.assertRegex(text, r"(?m)^\s*(import|from)\s+comfy_sdk\b")
        self.assertRegex(text, r"(?m)^\s*(import|from)\s+comfy_api_proxy\b")

    def test_no_direct_comfyui_endpoints(self):
        for path, text in self.files.items():
            self.assertIsNone(FORBIDDEN.search(text), f"{path} calls a ComfyUI endpoint directly; use the Comfy SDK")


if __name__ == "__main__":
    unittest.main()
