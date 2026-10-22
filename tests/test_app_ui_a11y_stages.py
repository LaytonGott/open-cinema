"""Browser test that the status panel stages show their state as text."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class StageTextTest(unittest.TestCase):
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
        h.fake.reset_cache()
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(h.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def test_stage_text_shows_state(self):
        fake, page = self.harness.fake, self.page
        fake.hold_at("SamplerCustomAdvanced")
        try:
            page.locator(tid("shot-description")).fill(DESCRIPTION)
            page.locator(tid("generate-button")).click()
            page.wait_for_function(
                "s => document.querySelector(s).dataset.state === 'active'", arg=tid("stage-generate")
            )
            generate = page.locator(tid("stage-generate")).text_content()
            self.assertTrue(generate.startswith("Generate video"), generate)
            self.assertTrue(generate.endswith("(active)"), generate)
            optics = page.locator(tid("stage-optics")).text_content()
            self.assertTrue(optics.startswith("Apply optics"), optics)
            self.assertIn("(pending)", optics)
        finally:
            fake.release()


if __name__ == "__main__":
    unittest.main()
