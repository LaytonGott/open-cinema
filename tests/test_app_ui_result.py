"""Browser test that the result state shows the after video."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
VIEWPORT = "[data-testid=viewport]"
PANEL = "[data-testid=status-panel]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


class ResultTest(unittest.TestCase):
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

    def test_result_video(self):
        h, page = self.harness, self.page
        page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
        page.locator("[data-testid=generate-button]").click()
        page.wait_for_function(
            "s => document.querySelector(s).dataset.state === 'result'", arg=VIEWPORT, timeout=60000
        )
        video = page.locator(f"{VIEWPORT} [data-testid=player] video[data-testid=after-video]")
        self.assertEqual(video.count(), 1)
        for prop in ("muted", "loop", "playsInline"):
            self.assertTrue(video.evaluate(f"v => v.{prop}"), prop)
        code, body = h.get("/api/shots")
        self.assertEqual(code, 200)
        url = body["shots"][0]["versions"][-1]["url"]
        src = video.get_attribute("src")
        self.assertTrue(src == url or src.endswith(url), src)
        resp = page.request.get(h.url + url)
        self.assertEqual(resp.status, 200)
        self.assertIn("video", resp.headers.get("content-type", ""))
        self.assertFalse(page.locator(PANEL).is_visible())


if __name__ == "__main__":
    unittest.main()
