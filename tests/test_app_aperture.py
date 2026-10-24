"""Browser test that the aperture slider drives form.aperture, its readout and the HUD."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness


def tid(name):
    return "[data-testid=%s]" % name


class ApertureTest(unittest.TestCase):
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

    def test_slider_updates_readout_and_hud(self):
        self.harness.reset()
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)
        page.wait_for_selector(tid("aperture-slider"))
        page.eval_on_selector(
            tid("aperture-slider"),
            "el => { el.value = '5'; el.dispatchEvent(new Event('input', {bubbles: true})); }",
        )
        page.wait_for_function(
            "s => document.querySelector(s).textContent.trim() === 'f/8'", arg=tid("aperture-value")
        )
        self.assertEqual(page.get_attribute(tid("aperture-slider"), "aria-valuetext"), "f/8")
        page.wait_for_function(
            "s => document.querySelector(s).textContent.includes('f/8')", arg=tid("hud")
        )


if __name__ == "__main__":
    unittest.main()
