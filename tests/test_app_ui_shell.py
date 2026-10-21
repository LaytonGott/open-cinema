"""Browser test of the page shell, design tokens and a clean load."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"


class ShellTest(unittest.TestCase):
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

    def test_shell_loads_cleanly(self):
        h = self.harness
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        errors, failed, urls = [], [], []
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("requestfailed", lambda r: failed.append(r.url))
        page.on("request", lambda r: urls.append(r.url))
        page.goto(h.url)
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )
        self.assertIn("Open Cinema", page.title())
        self.assertTrue(page.evaluate("document.documentElement.lang").startswith("en"))
        for sel in ("header", "#director", "#monitor", "#history"):
            self.assertTrue(page.is_visible(sel), sel)
        self.assertEqual(
            page.evaluate("getComputedStyle(document.body).backgroundColor"), "rgb(11, 12, 14)"
        )
        self.assertEqual(errors, [])
        self.assertEqual(failed, [])
        self.assertTrue(urls)
        for url in urls:
            self.assertTrue(url.startswith(h.url), url)


if __name__ == "__main__":
    unittest.main()
