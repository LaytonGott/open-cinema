"""Browser test of the focus rings and the tab order."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"
AMBER = "rgb(245, 165, 36)"

FOCUS_INFO = """() => {
  const el = document.activeElement;
  const cs = getComputedStyle(el);
  const own = el.getAttribute('data-testid');
  const owner = el.closest('[data-testid]');
  let group = null;
  for (const g of ['shot-description', 'camera-group', 'lens-group', 'framing-group',
                   'aperture-slider', 'generate-button']) {
    if (own === g || el.closest('[data-testid=' + g + ']')) { group = g; break; }
  }
  return {group: group, tag: el.tagName, testid: own || (owner && owner.dataset.testid),
          style: cs.outlineStyle, color: cs.outlineColor, width: parseFloat(cs.outlineWidth),
          shadow: cs.boxShadow};
}"""


class FocusRingTest(unittest.TestCase):
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
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 720})
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(self.harness.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )
        self.page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'empty'"
        )
        # Generate is disabled (so not focusable) without a description
        self.page.locator("[data-testid=shot-description]").fill("A woman walks through a rainy street")
        self.page.locator("[data-testid=logo-mark]").click(force=True)
        self.page.evaluate("() => document.activeElement && document.activeElement.blur()")

    def tab_stops(self, count):
        stops = []
        for _ in range(count):
            self.page.keyboard.press("Tab")
            stops.append(self.page.evaluate(FOCUS_INFO))
        return stops

    def test_first_stops_follow_the_form_order(self):
        stops = self.tab_stops(30)
        groups = []
        for s in stops:
            if s["group"] and s["group"] not in groups:
                groups.append(s["group"])
        self.assertEqual(
            groups[:6],
            ["shot-description", "camera-group", "lens-group", "framing-group",
             "aperture-slider", "generate-button"],
        )
        self.assertEqual([s["group"] for s in stops[:6]], groups[:6])

    def test_every_stop_has_an_amber_ring(self):
        for i, s in enumerate(self.tab_stops(30)):
            if s["tag"] == "BODY":  # the Tab cycle left the page
                continue
            with self.subTest(stop=i, testid=s["testid"]):
                outline = s["style"] != "none" and s["color"] == AMBER and s["width"] >= 1.5
                self.assertTrue(outline or AMBER in s["shadow"], s)

    def test_no_positive_tabindex(self):
        bad = self.page.evaluate(
            "() => [...document.querySelectorAll('*')].filter(e => e.tabIndex > 0).length"
        )
        self.assertEqual(bad, 0)


if __name__ == "__main__":
    unittest.main()
