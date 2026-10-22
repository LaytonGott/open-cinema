"""Browser test that the ComfyUI banner and a failed shot's error are announced as alerts with text."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
BANNER = "[data-testid=comfy-banner]"
VIEWPORT = "[data-testid=viewport]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."
MESSAGE = "Out of memory in Depth of Field"


class AlertsTest(unittest.TestCase):
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

    def wait_state(self, page, selector, state):
        page.wait_for_function(
            "([s, v]) => document.querySelector(s) && document.querySelector(s).dataset.state === v",
            arg=[selector, state],
        )

    def test_comfy_banner_is_alert(self):
        fake = self.harness.fake
        self.addCleanup(lambda: fake._thread is None and fake.start())
        fake.stop()
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)
        banner = page.locator(BANNER)
        banner.wait_for(state="visible")
        self.assertEqual(banner.get_attribute("role"), "alert")
        self.assertTrue(page.locator(STATUS).inner_text().strip())

    def test_failed_shot_text(self):
        h = self.harness
        h.fake.clear_failures()
        h.fake.release()
        deadline = time.time() + 30
        while time.time() < deadline:
            code, body = h.get("/api/shots")
            if code == 200 and all(s["status"] in TERMINAL for s in body["shots"]):
                break
            time.sleep(0.1)
        else:
            raise AssertionError("a shot was still active")
        h.reset()
        self.addCleanup(h.fake.clear_failures)
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(h.url)
        self.wait_state(page, STATUS, "ok")
        h.fake.fail("OpenOptics_DepthOfField", MESSAGE)
        page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
        page.locator("[data-testid=generate-button]").click()
        self.wait_state(page, VIEWPORT, "failed")
        self.assertTrue(page.locator("[data-testid=status-label]").inner_text().strip())
        error = page.locator("[data-testid=error-message]")
        self.assertEqual(error.get_attribute("role"), "alert")
        self.assertTrue(error.inner_text().strip())


if __name__ == "__main__":
    unittest.main()
