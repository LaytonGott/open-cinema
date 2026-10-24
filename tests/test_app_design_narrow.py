"""Browser test of the stacked layout below 900 px."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"

TOPS = """() => {
  const top = s => document.querySelector(s).getBoundingClientRect().top;
  return {
    header: top('[data-testid=app] > header'),
    viewport: top('[data-testid=viewport]'),
    director: top('#director'),
    history: top('[data-testid=history-list]'),
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  };
}"""


class NarrowLayoutTest(unittest.TestCase):
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
        self.harness.reset()
        self.page = self.browser.new_page(viewport={"width": 800, "height": 900})
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(self.harness.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def test_stacked_order_800(self):
        self.page.locator("[data-testid=history-new]").click()
        t = self.page.evaluate(TOPS)
        self.assertLess(t["header"], t["viewport"], t)
        self.assertLess(t["viewport"], t["director"], t)
        self.assertLess(t["director"], t["history"], t)
        self.assertLessEqual(t["scrollWidth"], t["innerWidth"], t)

    def test_viewport_ratio_and_history_scroll(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        m = self.page.evaluate("""() => {
          const v = document.querySelector('[data-testid=viewport]').getBoundingClientRect();
          const h = document.querySelector('[data-testid=history-list]');
          return {
            width: v.width, height: v.height, innerWidth: window.innerWidth,
            overflowX: getComputedStyle(h).overflowX,
            scrollWidth: document.documentElement.scrollWidth,
          };
        }""")
        self.assertAlmostEqual(m["width"], m["innerWidth"], delta=1, msg=m)
        self.assertAlmostEqual(m["width"] / m["height"], 20 / 11, delta=0.1, msg=m)
        self.assertIn(m["overflowX"], ("auto", "scroll"), m)
        self.assertLessEqual(m["scrollWidth"], m["innerWidth"], m)


if __name__ == "__main__":
    unittest.main()
