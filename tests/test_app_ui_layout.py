"""Browser test that the director page fits a 1280x720 window."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

WIDTH, HEIGHT = 1280, 720


def tid(name):
    return "[data-testid=%s]" % name


class LayoutTest(unittest.TestCase):
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
        self.page = self.browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(self.harness.url)
        self.page.wait_for_selector(tid("generate-button"))

    def box(self, name):
        box = self.page.locator(tid(name)).bounding_box()
        self.assertIsNotNone(box, name)
        return box

    def test_fits_1280x720(self):
        sizes = self.page.evaluate(
            "() => [document.documentElement.scrollHeight, document.documentElement.scrollWidth]"
        )
        self.assertLessEqual(sizes[0], HEIGHT)
        self.assertLessEqual(sizes[1], WIDTH)
        self.assertGreaterEqual(self.box("viewport")["width"], 560)
        generate = self.box("generate-button")
        self.assertGreaterEqual(generate["y"], 0)
        self.assertLessEqual(generate["y"] + generate["height"], HEIGHT)
        new = self.box("history-new")
        self.assertLessEqual(new["y"] + new["height"], HEIGHT)


if __name__ == "__main__":
    unittest.main()
