"""Tests for the requirement files and .gitignore at the repository root."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _lines(relative_path):
    """Return the stripped, non-empty lines of a repository file."""
    text = (ROOT / relative_path).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


class AppRequirementsTest(unittest.TestCase):
    def test_pins_comfy_packages(self):
        lines = _lines("app/requirements.txt")
        self.assertIn("comfy-sdk==0.5.0", lines)
        self.assertIn("comfy-api-proxy==0.1.6", lines)

    def test_has_no_aiohttp_line(self):
        for line in _lines("app/requirements.txt"):
            self.assertNotIn("aiohttp", line.lower())


class TestRequirementsTest(unittest.TestCase):
    def test_lists_test_packages(self):
        lines = [line.lower() for line in _lines("requirements-test.txt")]
        for package in ("playwright", "pillow", "numpy"):
            self.assertTrue(
                any(line.startswith(package) for line in lines), package
            )

    def test_includes_app_requirements(self):
        self.assertIn("-r app/requirements.txt", _lines("requirements-test.txt"))


class GitignoreTest(unittest.TestCase):
    def test_ignores_app_data_and_screenshots(self):
        lines = _lines(".gitignore")
        self.assertIn("app/data/", lines)
        self.assertIn("app/screenshots/", lines)


if __name__ == "__main__":
    unittest.main()
