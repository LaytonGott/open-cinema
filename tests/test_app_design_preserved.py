"""Checks that the identifiers and texts from docs/app-spec.md survive in the frontend."""
import re
import time
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

ROOT = Path(__file__).resolve().parent.parent
GENERATE = "[data-testid=generate-button]"
STATUS = "[data-testid=comfy-status]"
ATTRIBUTE_PREFIXES = ("data-", "aria-")


def spec_testids():
    """Return the sorted data-testid names the spec writes in backticks or as data-testid="...".

    The backtick scan starts at the line that defines the data-testid rule (section 5), so names
    from earlier sections (route and option names) are not counted; attribute names such as
    data-state or aria-checked are not test ids.
    """
    lines = (ROOT / "docs" / "app-spec.md").read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if "Every element below has a `data-testid`" in line)
    end = next((i for i, line in enumerate(lines) if line.startswith("## 7.")), len(lines))
    names = set()
    for line in lines[start:end]:
        names.update(re.findall(r'data-testid="([^"]+)"', line))
        for name in re.findall(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`", line):
            if not name.startswith(ATTRIBUTE_PREFIXES):
                names.add(name)
    return sorted(names)


class SpecIdentifiersTest(unittest.TestCase):
    def test_spec_testids_present(self):
        static = ROOT / "app" / "static"
        files = [static / "index.html", *sorted(static.rglob("*.js"))]
        source = "".join(f.read_text(encoding="utf-8") for f in files)
        names = spec_testids()
        self.assertGreater(len(names), 20)
        missing = [n for n in names if n not in source]
        self.assertEqual(missing, [])


class KeyboardFlowTest(unittest.TestCase):
    harness = None
    pw = None
    browser = None

    @classmethod
    def setUpClass(cls):
        try:
            cls.harness = AppHarness().start()
            cls.pw = sync_playwright().start()
            cls.browser = cls.pw.chromium.launch(headless=True)
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for closer in (
            lambda: cls.browser and cls.browser.close(),
            lambda: cls.pw and cls.pw.stop(),
            lambda: cls.harness and cls.harness.stop(),
        ):
            try:
                closer()
            except Exception:
                pass
        cls.browser = cls.pw = cls.harness = None

    def test_keyboard_flow(self):
        self.harness.reset()
        page = self.browser.new_page(viewport={"width": 1280, "height": 720})
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )
        page.locator("[data-testid=history-new]").click()
        page.wait_for_function("() => document.querySelector('[data-testid=viewport]').dataset.state === 'empty'")

        button = page.locator(GENERATE)
        self.assertEqual(button.inner_text().strip(), "Generate shot")

        # a camera option changes its checked state with Space
        radio = page.locator("[data-testid=camera-group] [role=radio]").nth(1)
        radio.wait_for()
        value = radio.get_attribute("data-value")
        self.assertNotEqual(radio.get_attribute("aria-checked"), "true")
        radio.focus()
        radio.press("Space")
        page.wait_for_function(
            "v => document.querySelector(`[data-testid=camera-group] [data-value=\"${v}\"]`)"
            ".getAttribute('aria-checked') === 'true'",
            arg=value,
        )

        # typing a description enables Generate, and Enter on the button starts a shot
        page.locator("[data-testid=shot-description]").fill("A dog runs on a beach")
        page.wait_for_function("s => !document.querySelector(s).disabled", arg=GENERATE)
        button.focus()
        button.press("Enter")
        try:
            page.locator("[data-testid=history-item]").first.wait_for()
        finally:
            self.harness.fake.release()
        code, body = self.harness.get("/api/shots")
        self.assertEqual(code, 200)
        deadline = time.time() + 15
        while time.time() < deadline and not body["shots"]:
            time.sleep(0.1)
            code, body = self.harness.get("/api/shots")
        self.assertEqual(len(body["shots"]), 1)
        self.harness.wait_for_shot(body["shots"][0]["id"])


if __name__ == "__main__":
    unittest.main()
