"""Browser test of a failed re-apply and the retry."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."
MESSAGE = "Out of memory in Depth of Field"
F16_INDEX = "7"


def tid(name):
    return "[data-testid=%s]" % name


def set_slider(page, index):
    page.locator(tid("reapply-slider")).evaluate(
        "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); }",
        index,
    )


class ReapplyFailureUiTest(unittest.TestCase):
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

    def wait_status(self, page, text):
        page.wait_for_function(
            "([s, t]) => document.querySelector(s) && document.querySelector(s).textContent.trim() === t",
            arg=[tid("reapply-status"), text],
        )

    def wait_status_contains(self, page, text):
        page.wait_for_function(
            "([s, t]) => document.querySelector(s) && document.querySelector(s).textContent.includes(t)",
            arg=[tid("reapply-status"), text],
        )

    def chips(self, page):
        return page.eval_on_selector_all(
            tid("version-chip"),
            "els => els.map(e => [e.dataset.aperture, e.getAttribute('aria-pressed')])",
        )

    def test_failed_reapply_shows_error_then_retry_adds_chip(self):
        h = self.harness
        h.fake.reset_cache()
        page = self.browser.new_page()
        self.addCleanup(page.close)
        self.addCleanup(h.fake.clear_failures)
        page.set_default_timeout(15000)
        page.goto(h.url)
        page.locator(tid("shot-description")).fill(DESCRIPTION)
        page.locator(tid("generate-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )
        self.wait_status(page, "Applied f/2.8")
        chips_before = self.chips(page)
        self.assertEqual(len(chips_before), 1)

        h.fake.reset_cache()
        h.fake.fail("OpenOptics_DepthOfField", MESSAGE)
        set_slider(page, F16_INDEX)
        page.locator(tid("reapply-button")).click()
        self.wait_status_contains(page, MESSAGE)
        self.assertEqual(
            page.locator(tid("viewport")).get_attribute("data-state"), "result"
        )
        self.assertEqual(self.chips(page), chips_before)
        self.assertTrue(page.locator(tid("reapply-button")).is_enabled())

        page.reload()
        page.locator(tid("reapply-status")).wait_for(state="visible")
        self.wait_status_contains(page, MESSAGE)

        h.fake.clear_failures()
        h.fake.reset_cache()
        set_slider(page, F16_INDEX)
        page.locator(tid("reapply-button")).click()
        page.locator(tid("version-chip") + "[data-aperture='16']").wait_for()
        self.wait_status(page, "Applied f/16")
        self.assertEqual(len(self.chips(page)), 2)


if __name__ == "__main__":
    unittest.main()
