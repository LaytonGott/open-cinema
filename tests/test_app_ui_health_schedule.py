"""Browser test of the scheduled health checks: recovery and focus re-check."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"
RETRY = "[data-testid=comfy-retry]"


class HealthScheduleTest(unittest.TestCase):
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

    def wait_state(self, page, state, timeout=15000):
        page.wait_for_function(
            "([s, v]) => document.querySelector(s) && document.querySelector(s).dataset.state === v",
            arg=[STATUS, state],
            timeout=timeout,
        )

    def test_down_recovers_without_click(self):
        fake = self.harness.fake
        self.addCleanup(lambda: fake._thread is None and fake.start())
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)
        self.wait_state(page, "ok")

        fake.stop()
        page.dispatch_event(RETRY, "click")
        self.wait_state(page, "down")

        fake.start()
        self.wait_state(page, "ok", timeout=12000)

    def test_focus_triggers_health_request(self):
        counts = []
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.on("request", lambda r: r.url.endswith("/api/health") and counts.append(r.url))
        page.goto(self.harness.url)
        self.wait_state(page, "ok")

        before = len(counts)
        page.evaluate("window.dispatchEvent(new Event('focus'))")
        deadline = time.monotonic() + 10
        while len(counts) <= before and time.monotonic() < deadline:
            page.wait_for_timeout(50)
        self.assertGreater(len(counts), before)


if __name__ == "__main__":
    unittest.main()
