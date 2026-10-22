"""Browser test of the status panel elapsed time: it ticks, stops and survives a reload."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
PANEL = "[data-testid=status-panel]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."
CLOCK = r"^\d+:\d{2}$"


def tid(name):
    return "[data-testid=%s]" % name


class ElapsedTest(unittest.TestCase):
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

    def start_held_shot(self):
        page = self.page
        self.harness.fake.hold_at("SamplerCustomAdvanced")
        page.locator(tid("shot-description")).fill(DESCRIPTION)
        page.locator(tid("generate-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s).dataset.status === 'generating'", arg=PANEL
        )

    def test_elapsed_ticks_while_held(self):
        fake, page = self.harness.fake, self.page
        try:
            self.start_held_shot()
            elapsed = page.locator(tid("elapsed"))
            first = elapsed.text_content()
            self.assertRegex(first, CLOCK)
            deadline = time.time() + 3
            changed = False
            while time.time() < deadline:
                text = elapsed.text_content()
                self.assertRegex(text, CLOCK)
                if text != first:
                    changed = True
                    break
                time.sleep(0.1)
            self.assertTrue(changed, "elapsed did not change within 3 s")
        finally:
            fake.release()

    def test_elapsed_survives_reload(self):
        fake, page = self.harness.fake, self.page
        try:
            self.start_held_shot()
            time.sleep(2)
            page.reload()
            page.wait_for_function(
                "s => { const e = document.querySelector(s); return e && !e.hidden }", arg=PANEL
            )
            text = page.locator(tid("elapsed")).text_content()
            self.assertRegex(text, CLOCK)
            self.assertNotEqual(text, "0:00")
        finally:
            fake.release()

    def test_elapsed_constant_after_cancel(self):
        fake, page = self.harness.fake, self.page
        try:
            self.start_held_shot()
            time.sleep(1.2)
            page.locator(tid("cancel-button")).click()
            page.wait_for_function(
                "s => document.querySelector(s).dataset.status === 'cancelled'", arg=PANEL
            )
        finally:
            fake.release()
        elapsed = page.locator(tid("elapsed"))
        first = elapsed.text_content()
        deadline = time.time() + 2.5
        while time.time() < deadline:
            self.assertEqual(elapsed.text_content(), first)
            time.sleep(0.25)


if __name__ == "__main__":
    unittest.main()
