"""Browser test of the re-apply status text."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class ReapplyStatusTest(unittest.TestCase):
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

    def test_finished_shot_shows_applied_status(self):
        h = self.harness
        h.reset()
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(h.url)
        page.locator(tid("shot-description")).fill(DESCRIPTION)
        page.locator(tid("generate-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )
        status = page.locator(tid("reapply-status"))
        status.wait_for(state="visible")
        self.assertEqual(status.text_content(), "Applied f/2.8")
        self.assertEqual(status.get_attribute("role"), "status")

    def test_applying_then_applied_status_text(self):
        h = self.harness
        h.reset()
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(h.url)
        page.locator(tid("shot-description")).fill(DESCRIPTION)
        page.locator(tid("generate-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )
        status = page.locator(tid("reapply-status"))
        slider = page.locator(tid("reapply-slider"))
        status.wait_for(state="visible")
        self.assertEqual(status.get_attribute("aria-live"), "polite")
        h.fake.hold_at("OpenOptics_DepthOfField")
        try:
            slider.evaluate(
                "el => { el.value = '5'; el.dispatchEvent(new Event('input', {bubbles: true})); }"
            )
            page.locator(tid("reapply-button")).click()
            page.wait_for_function(
                "s => document.querySelector(s) && document.querySelector(s).textContent.trim() === 'Applying f/8 ...'",
                arg=tid("reapply-status"),
            )
            self.assertEqual(
                page.locator(tid("viewport")).get_attribute("data-state"), "result"
            )
        finally:
            h.fake.release()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).textContent.trim() === 'Applied f/8'",
            arg=tid("reapply-status"),
        )

    def test_reload_during_reapply_shows_target(self):
        h = self.harness
        h.reset()
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(h.url)
        page.locator(tid("shot-description")).fill(DESCRIPTION)
        page.locator(tid("generate-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )
        slider = page.locator(tid("reapply-slider"))
        h.fake.hold_at("OpenOptics_DepthOfField")
        try:
            slider.evaluate(
                "el => { el.value = '5'; el.dispatchEvent(new Event('input', {bubbles: true})); }"
            )
            page.locator(tid("reapply-button")).click()
            page.wait_for_function(
                "s => document.querySelector(s) && document.querySelector(s).textContent.trim() === 'Applying f/8 ...'",
                arg=tid("reapply-status"),
            )
            page.reload()
            # The requested aperture is not kept across a reload: the status shows the slider's value.
            page.wait_for_function(
                "([s, v]) => { const value = document.querySelector(v) && document.querySelector(v).textContent.trim();"
                " return !!value && !!document.querySelector(s) &&"
                " document.querySelector(s).textContent.trim() === 'Applying ' + value + ' ...'; }",
                arg=[tid("reapply-status"), tid("reapply-value")],
            )
        finally:
            h.fake.release()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).textContent.trim() === 'Applied f/8'",
            arg=tid("reapply-status"),
        )


if __name__ == "__main__":
    unittest.main()
