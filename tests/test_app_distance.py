"""Browser test of the subject distance readout."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

SEL = "[data-testid=subject-distance]"


class DistanceTest(unittest.TestCase):
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
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 720})
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(self.harness.url)
        self.page.wait_for_selector(SEL + "[data-metres]")

    def metres(self):
        return self.page.get_attribute(SEL, "data-metres")

    def test_reads_distance_after_load(self):
        self.assertRegex(self.page.inner_text(SEL).strip(), r"^Subject about \d")
        float(self.metres())

    def test_lens_change_updates_metres(self):
        before = self.metres()
        self.page.click("[data-testid=lens-group] [data-value='24']")
        self.page.wait_for_function(
            "([sel, old]) => document.querySelector(sel).getAttribute('data-metres') !== old",
            arg=[SEL, before],
        )
        self.assertNotEqual(self.metres(), before)
        self.assertRegex(self.page.inner_text(SEL).strip(), r"^Subject about \d")


if __name__ == "__main__":
    unittest.main()
