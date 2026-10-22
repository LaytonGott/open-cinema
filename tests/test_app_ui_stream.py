"""Browser test that a shot still finishes when the event stream ends at once with no events."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
VIEWPORT = "[data-testid=viewport]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


class StreamTest(unittest.TestCase):
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

    def test_shot_finishes_when_event_stream_is_empty(self):
        h, fake, page = self.harness, self.harness.fake, self.page
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.route(
            "**/api/shots/*/events",
            lambda route: route.fulfill(status=200, content_type="text/event-stream", body=""),
        )
        page.goto(h.url)
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )
        fake.hold_at("SamplerCustomAdvanced")
        shot_id = None
        try:
            page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
            page.locator("[data-testid=generate-button]").click()
            page.wait_for_function(
                "s => document.querySelector(s).dataset.state === 'working'", arg=VIEWPORT
            )
            code, body = h.get("/api/shots")
            if code == 200 and body["shots"]:
                shot_id = body["shots"][0]["id"]
            fake.release()
            page.wait_for_function(
                "s => document.querySelector(s).dataset.state === 'result'", arg=VIEWPORT
            )
            self.assertEqual(errors, [])
        finally:
            fake.release()
        if shot_id is not None:
            h.wait_for_shot(shot_id, "done")


if __name__ == "__main__":
    unittest.main()
