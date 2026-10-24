"""Browser test that the REC dot shows while a shot works and goes away after."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
DOT = "[data-testid=record-dot]"
PANEL = "[data-testid=status-panel]"
STYLE = "e => { const s = getComputedStyle(e); return [s.animationName, s.animationIterationCount]; }"


class RecDotTest(unittest.TestCase):
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

    def open_page(self, **context_args):
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
        context = self.browser.new_context(**context_args)
        self.addCleanup(context.close)
        page = context.new_page()
        page.set_default_timeout(15000)
        page.goto(h.url)
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )
        return page

    def start_held_shot(self, page):
        h = self.harness
        h.fake.hold_at("SamplerCustomAdvanced")
        page.locator("[data-testid=shot-description]").fill("A rider crosses a foggy salt flat at dawn.")
        page.locator("[data-testid=generate-button]").click()
        deadline = time.time() + 30
        shot_id = None
        while time.time() < deadline and shot_id is None:
            code, body = h.get("/api/shots")
            if code == 200 and body["shots"]:
                shot_id = body["shots"][0]["id"]
            time.sleep(0.05)
        self.assertIsNotNone(shot_id, "no shot was created")
        h.wait_until(shot_id, lambda r: r["status"] == "generating", what="shot generating")
        return shot_id

    def test_dot_visible_only_while_working(self):
        page = self.open_page()
        self.assertFalse(page.locator(DOT).is_visible())
        shot_id = self.start_held_shot(page)
        try:
            page.locator(DOT).wait_for(state="visible")
            name, count = page.locator(DOT).evaluate(STYLE)
            self.assertNotEqual(name, "none")
            self.assertEqual(count, "infinite")
            self.assertTrue(page.locator(PANEL).get_by_text("REC", exact=True).is_visible())
        finally:
            self.harness.fake.release()
        self.harness.wait_for_shot(shot_id, "done")
        page.locator(DOT).wait_for(state="hidden")
        self.assertFalse(page.locator(DOT).is_visible())

    def test_reduced_motion_turns_animation_off(self):
        page = self.open_page(reduced_motion="reduce")
        shot_id = self.start_held_shot(page)
        try:
            page.locator(DOT).wait_for(state="visible")
            name, _ = page.locator(DOT).evaluate(STYLE)
            self.assertEqual(name, "none")
        finally:
            self.harness.fake.release()
        self.harness.wait_for_shot(shot_id, "done")


if __name__ == "__main__":
    unittest.main()
