"""Browser test of the app starting while ComfyUI is down."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"
BANNER = "[data-testid=comfy-banner]"
GENERATE = "[data-testid=generate-button]"


class _ColdStartHarness:
    """Class setup: the app started while the fake ComfyUI is down, plus a headless browser."""
    harness = None
    pw = None
    browser = None
    fake_url = None

    @classmethod
    def setUpClass(cls):
        try:
            cls.harness = AppHarness().start()
            cls.fake_url = cls.harness.fake.url
            cls.harness.fake.stop()
            cls.harness.restart_app()
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

class ColdStartTest(_ColdStartHarness, unittest.TestCase):
    def test_log_says_where_the_app_and_comfyui_are(self):
        expected = f"Open Cinema is running at {self.harness.url} (ComfyUI at {self.fake_url})"
        self.assertIn(expected, self.harness.log())

    def test_page_shows_comfyui_down_and_disables_generate(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)
        page.wait_for_function(
            "([s, v]) => document.querySelector(s) && document.querySelector(s).dataset.state === v",
            arg=[STATUS, "down"],
        )
        banner = page.locator(BANNER)
        banner.wait_for(state="visible")
        self.assertIn(f"Can't reach ComfyUI at {self.fake_url}", banner.inner_text())
        page.fill("[data-testid=shot-description]", "A lone rider on a ridge at dusk")
        self.assertTrue(page.locator(GENERATE).is_disabled())


class RetryAfterColdStartTest(_ColdStartHarness, unittest.TestCase):
    def test_retry_connects_without_reloading(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)
        wait_state = "([s, v]) => document.querySelector(s) && document.querySelector(s).dataset.state === v"
        page.wait_for_function(wait_state, arg=[STATUS, "down"])
        self.harness.fake.start()
        page.click("[data-testid=comfy-retry]")
        page.wait_for_function(wait_state, arg=[STATUS, "ok"])
        self.assertIn("ComfyUI: connected", page.locator(STATUS).inner_text())
        page.locator(BANNER).wait_for(state="hidden")
        page.fill("[data-testid=shot-description]", "A lone rider on a ridge at dusk")
        self.assertTrue(page.locator(GENERATE).is_enabled())


if __name__ == "__main__":
    unittest.main()
