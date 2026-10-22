"""Browser test that history, new-shot, cancel and retry controls have text after a finished shot."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
VIEWPORT = "[data-testid=viewport]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


class A11yDoneTest(unittest.TestCase):
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
        h = self.harness
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
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(h.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def test_finished_shot_controls_have_names(self):
        fake, page = self.harness.fake, self.page
        page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
        page.locator("[data-testid=generate-button]").click()
        page.wait_for_function(
            "s => document.querySelector(s).dataset.state === 'result'", arg=VIEWPORT
        )
        for testid in ("history-item", "history-new"):
            items = page.locator("[data-testid=%s]" % testid)
            self.assertGreater(items.count(), 0, testid)
            for i in range(items.count()):
                if items.nth(i).is_visible():
                    self.assertTrue(items.nth(i).inner_text().strip(), testid + " has no text")
        cancel = page.locator("[data-testid=cancel-button]")
        retry = page.locator("[data-testid=retry-button]")
        fake.hold_at("SamplerCustomAdvanced")
        try:
            page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
            page.locator("[data-testid=generate-button]").click()
            cancel.wait_for(state="visible")
            self.assertTrue(cancel.inner_text().strip())
            cancel.click()
            retry.wait_for(state="visible")
            self.assertTrue(retry.inner_text().strip())
        finally:
            fake.release()


if __name__ == "__main__":
    unittest.main()
