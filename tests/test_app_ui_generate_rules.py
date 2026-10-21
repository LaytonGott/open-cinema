"""Browser test of the Generate button enable rules."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"


class GenerateRulesTest(unittest.TestCase):
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
        self.harness.fake.release()
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(self.harness.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def ta(self):
        return self.page.locator("[data-testid=shot-description]")

    def button(self):
        return self.page.locator("[data-testid=generate-button]")

    def wait_button(self, disabled):
        self.page.wait_for_function(
            "d => document.querySelector('[data-testid=generate-button]').disabled === d", arg=disabled
        )

    def test_disabled_and_enabled_by_description(self):
        cases = [("", True), ("ab", True), ("   ab  ", True), ("A dog runs", False)]
        for text, disabled in cases:
            with self.subTest(text=text):
                self.ta().fill(text)
                self.wait_button(disabled)
                self.assertEqual(self.button().is_disabled(), disabled)

    def test_held_run_disables_button_but_textarea_accepts_typing(self):
        fake = self.harness.fake
        fake.hold_at("SamplerCustomAdvanced")
        try:
            self.ta().fill("A dog runs")
            self.wait_button(False)
            self.button().click()
            self.wait_button(True)
            self.ta().fill("A cat sleeps on a sofa")
            self.assertEqual(self.ta().input_value(), "A cat sleeps on a sofa")
            self.assertTrue(self.button().is_disabled())
        finally:
            fake.release()
        self.wait_button(False)
        self.assertEqual(self.ta().input_value(), "A cat sleeps on a sofa")


if __name__ == "__main__":
    unittest.main()
