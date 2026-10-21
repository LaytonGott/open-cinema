"""Browser test that submitting while ComfyUI is down marks it down and shows the submit error."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


class SubmitErrorsTest(unittest.TestCase):
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

    def setUp(self):
        code, body = self.harness.get("/api/shots")
        for shot in (body or {}).get("shots", []) if code == 200 else []:
            self.harness.request("DELETE", "/api/shots/" + shot["id"])
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(self.harness.url)
        self.wait_state("comfy-status", "ok")

    def wait_state(self, testid, state):
        self.page.wait_for_function(
            "([s, v]) => document.querySelector(s) && document.querySelector(s).dataset.state === v",
            arg=[f"[data-testid={testid}]", state],
        )

    def test_submit_while_comfy_down(self):
        fake, page = self.harness.fake, self.page
        fake.stop()
        self.addCleanup(fake.start)
        page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
        page.locator("[data-testid=generate-button]").click()
        self.wait_state("comfy-status", "down")
        self.assertTrue(page.locator("[data-testid=comfy-banner]").is_visible())
        error = page.locator("[data-testid=submit-error]")
        self.assertTrue(error.is_visible())
        self.assertTrue(error.inner_text().strip())
        self.assertEqual(page.locator("[data-testid=viewport]").get_attribute("data-state"), "empty")

    def test_retry_after_comfy_returns(self):
        fake, page = self.harness.fake, self.page
        fake.stop()
        restored = False
        try:
            page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
            page.locator("[data-testid=generate-button]").click()
            self.wait_state("comfy-status", "down")
            fake.start()
            restored = True
            page.locator("[data-testid=comfy-retry]").click()
            self.wait_state("comfy-status", "ok")
            page.locator("[data-testid=generate-button]").click()
            self.wait_state("viewport", "result")
        finally:
            if not restored:
                fake.start()


if __name__ == "__main__":
    unittest.main()
