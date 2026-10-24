"""Browser tests of the design tokens, fonts and that the page makes no foreign requests."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

TOKENS = {
    "--bg": "#0b0c0e",
    "--surface": "#14161a",
    "--raised": "#1b1e24",
    "--line": "#262a31",
    "--text": "#e9e6df",
    "--muted": "#9097a2",
    "--accent": "#f5a524",
    "--ok": "#5ad19a",
    "--danger": "#ff6b6b",
}


def tid(name):
    return "[data-testid=%s]" % name


class DesignTest(unittest.TestCase):
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

    def open_page(self, width, height):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        self.requests = []
        self.errors = []
        page.on("request", lambda request: self.requests.append(request.url))
        page.on("console", lambda msg: msg.type == "error" and self.errors.append(msg.text))
        page.goto(self.harness.url)
        page.wait_for_selector(tid("generate-button"))
        return page

    def test_tokens_on_root(self):
        page = self.open_page(1280, 720)
        for name, expected in TOKENS.items():
            value = page.evaluate(
                "n => getComputedStyle(document.documentElement).getPropertyValue(n)", name
            )
            self.assertEqual(value.strip().lower(), expected, name)

    def test_body_background(self):
        page = self.open_page(1280, 720)
        background = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
        self.assertEqual(background, "rgb(11, 12, 14)")

    def test_fonts(self):
        page = self.open_page(1280, 720)
        family = "s => getComputedStyle(document.querySelector(s)).fontFamily"
        for name in ("hud", "aperture-value", "subject-distance"):
            value = page.evaluate(family, tid(name))
            self.assertIn("Consolas", value, name)
            self.assertIn("monospace", value, name)
        body = page.evaluate(family, "body")
        self.assertIn("Segoe UI", body)
        self.assertIn("system-ui", body)

    def test_no_foreign_requests(self):
        self.open_page(1280, 720)
        self.assertTrue(self.requests)
        for url in self.requests:
            if url.startswith("data:") or url.startswith("blob:"):
                continue
            self.assertTrue(url.startswith(self.harness.url), url)
        self.assertEqual(self.errors, [])


if __name__ == "__main__":
    unittest.main()
