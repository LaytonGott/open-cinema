"""Browser test that the cancel button shows only while a shot is working and cancelling ends in the cancelled state."""
import json
import time
import unittest
import urllib.request

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
VIEWPORT = "[data-testid=viewport]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


class CancelUiTest(unittest.TestCase):
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

    @staticmethod
    def _wait_running(fake):
        # cancelling a job ComfyUI has not started yet only drops it from the queue, so wait until it runs
        deadline = time.time() + 15
        while time.time() < deadline:
            with urllib.request.urlopen(fake.url + "/queue", timeout=5) as resp:
                if json.load(resp)["queue_running"]:
                    return
            time.sleep(0.05)
        raise AssertionError("the job never started running")

    def test_cancel_button_and_cancelled_state(self):
        fake, page = self.harness.fake, self.page
        cancel = page.locator("[data-testid=cancel-button]")
        self.assertTrue(cancel.is_hidden())
        fake.hold_at("SamplerCustomAdvanced")
        try:
            page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
            page.locator("[data-testid=generate-button]").click()
            page.wait_for_function(
                "s => document.querySelector(s).dataset.state === 'working'", arg=VIEWPORT
            )
            cancel.wait_for(state="visible")
            self._wait_running(fake)
            cancel.click()
            page.wait_for_function(
                "s => document.querySelector(s).dataset.state === 'cancelled'", arg=VIEWPORT
            )
        finally:
            fake.release()
        self.assertEqual(page.locator("[data-testid=status-label]").inner_text().strip(), "Cancelled.")
        self.assertEqual(page.locator("[data-testid=retry-button]").inner_text().strip(), "Try again")
        self.assertTrue(page.locator("[data-testid=generate-button]").is_enabled())
        self.assertTrue(cancel.is_hidden())


if __name__ == "__main__":
    unittest.main()
