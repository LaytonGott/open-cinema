"""Browser test of the ComfyUI down banner and its retry button."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"
BANNER = "[data-testid=comfy-banner]"
RETRY = "[data-testid=comfy-retry]"
GENERATE = "[data-testid=generate-button]"


class ComfyBannerTest(unittest.TestCase):
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

    def wait_state(self, page, state):
        page.wait_for_function(
            "([s, v]) => document.querySelector(s) && document.querySelector(s).dataset.state === v",
            arg=[STATUS, state],
        )

    def test_banner_shows_when_down_and_retry_recovers(self):
        fake = self.harness.fake
        self.addCleanup(lambda: fake._thread is None and fake.start())
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)
        self.wait_state(page, "ok")
        self.assertTrue(page.locator(BANNER).is_hidden())
        page.fill("[data-testid=shot-description]", "A lone rider on a ridge at dusk")
        self.assertTrue(page.locator(GENERATE).is_enabled())

        fake_url = fake.url
        fake.stop()
        page.dispatch_event(RETRY, "click")
        self.wait_state(page, "down")
        banner = page.locator(BANNER)
        banner.wait_for(state="visible")
        self.assertEqual(banner.get_attribute("role"), "alert")
        text = banner.inner_text()
        self.assertIn("Can't reach ComfyUI at", text)
        self.assertIn(fake_url, text)
        self.assertTrue(page.locator(GENERATE).is_disabled())

        fake.start()
        page.click(RETRY)
        self.wait_state(page, "ok")
        banner.wait_for(state="hidden")
        self.assertTrue(page.locator(GENERATE).is_enabled())


if __name__ == "__main__":
    unittest.main()
