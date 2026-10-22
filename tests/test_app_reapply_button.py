"""Browser test of the re-apply button's disabled rule."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class ReapplyButtonTest(unittest.TestCase):
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

    def test_disabled_until_slider_moves_to_another_stop(self):
        h = self.harness
        h.fake.reset_cache()
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
        button = page.locator(tid("reapply-button"))
        slider = page.locator(tid("reapply-slider"))
        button.wait_for(state="visible")
        self.assertEqual(button.text_content(), "Apply aperture")
        self.assertTrue(button.is_disabled())
        slider.focus()
        slider.press("ArrowRight")
        self.assertTrue(button.is_enabled())
        slider.press("ArrowLeft")
        self.assertTrue(button.is_disabled())


if __name__ == "__main__":
    unittest.main()
