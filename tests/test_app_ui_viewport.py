"""Browser tests of the viewport states, crop marks and aspect ratio."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
VIEWPORT = "[data-testid=viewport]"


class ViewportTest(unittest.TestCase):
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

    def state(self):
        return self.page.locator(VIEWPORT).get_attribute("data-state")

    def wait_state(self, value):
        self.page.wait_for_function(
            "([s, v]) => document.querySelector(s).dataset.state === v", arg=[VIEWPORT, value]
        )

    def test_fresh_page_is_empty_with_hint_and_crop_marks(self):
        page = self.page
        self.assertEqual(self.state(), "empty")
        self.assertTrue(page.locator("[data-testid=viewport-hint]").is_visible())
        self.assertEqual(page.locator("[data-testid=crop-mark]").count(), 4)

    def test_aspect_ratio(self):
        box = self.page.locator(VIEWPORT).bounding_box()
        self.assertAlmostEqual(box["width"] / box["height"], 20 / 11, delta=0.05)

    def test_working_then_result(self):
        h, fake, page = self.harness, self.harness.fake, self.page
        fake.hold_at("SamplerCustomAdvanced")
        shot_id = None
        try:
            page.locator("[data-testid=shot-description]").fill("A rider crosses a foggy salt flat at dawn.")
            page.locator("[data-testid=generate-button]").click()
            self.wait_state("working")
            deadline = time.time() + 30
            while time.time() < deadline and shot_id is None:
                code, body = h.get("/api/shots")
                if code == 200 and body["shots"]:
                    shot_id = body["shots"][0]["id"]
                time.sleep(0.05)
            self.assertIsNotNone(shot_id, "no shot was created")
        finally:
            fake.release()
        h.wait_for_shot(shot_id, "done")
        self.wait_state("result")
        self.assertEqual(self.state(), "result")


if __name__ == "__main__":
    unittest.main()
