"""Browser test of the status panel while a shot generates and after the result arrives."""
import re
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
VIEWPORT = "[data-testid=viewport]"
PANEL = "[data-testid=status-panel]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class PanelTest(unittest.TestCase):
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

    def test_panel_while_generating_then_hidden_in_result(self):
        fake, page = self.harness.fake, self.page
        fake.hold_at("SamplerCustomAdvanced")
        try:
            page.locator(tid("shot-description")).fill(DESCRIPTION)
            page.locator(tid("generate-button")).click()
            page.wait_for_function(
                "s => document.querySelector(s).dataset.state === 'working'", arg=VIEWPORT
            )
            page.wait_for_function(
                "s => document.querySelector(s).dataset.status === 'generating'", arg=PANEL
            )
            panel = page.locator(PANEL)
            self.assertEqual(panel.get_attribute("data-status"), "generating")
            self.assertEqual(page.locator(tid("stage-generate")).get_attribute("data-state"), "active")
            self.assertEqual(page.locator(tid("stage-optics")).get_attribute("data-state"), "pending")
            bar = page.locator(tid("progress-bar"))
            self.assertEqual(bar.get_attribute("role"), "progressbar")
            now = bar.get_attribute("aria-valuenow")
            self.assertRegex(now, r"^\d+(\.\d+)?$")
            self.assertTrue(0 <= float(now) <= 100)
            self.assertTrue(page.locator(tid("record-dot")).is_visible())
            elapsed = page.locator(tid("elapsed"))
            first = elapsed.text_content()
            self.assertRegex(first, r"^\d+:\d{2}$")
            deadline = time.time() + 10
            changed = False
            while time.time() < deadline:
                text = elapsed.text_content()
                self.assertRegex(text, r"^\d+:\d{2}$")
                if text != first:
                    changed = True
                    break
                time.sleep(0.1)
            self.assertTrue(changed, "elapsed did not change")
        finally:
            fake.release()
        page.wait_for_function(
            "s => document.querySelector(s).dataset.state === 'result'", arg=VIEWPORT, timeout=30000
        )
        self.assertTrue(page.locator(PANEL).is_hidden())
        self.assertTrue(page.locator(tid("record-dot")).is_hidden())


if __name__ == "__main__":
    unittest.main()
