"""Browser test that the subject-distance readout and the focus-ruler marker follow lens and framing."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness


def tid(name):
    return "[data-testid=%s]" % name


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

    def new_page(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)
        return page

    def read(self, page):
        """Return (text, data-metres, marker left edge in px)."""
        el = page.locator(tid("subject-distance"))
        box = page.locator(tid("focus-marker")).bounding_box()
        return el.text_content(), el.get_attribute("data-metres"), box["x"]

    def wait_text_not(self, page, old):
        page.wait_for_function(
            "([s, old]) => { const e = document.querySelector(s);"
            " return e && e.textContent.trim() !== '' && e.textContent !== old; }",
            arg=[tid("subject-distance"), old],
        )
        # the marker moves with a CSS transition; wait until its position stops changing
        page.evaluate("window.__mx = null")
        page.wait_for_function(
            "s => { const x = document.querySelector(s).getBoundingClientRect().x;"
            " const prev = window.__mx; window.__mx = x; return prev === x; }",
            arg=tid("focus-marker"),
            polling=100,
        )

    def pick(self, page, group, value):
        before = page.locator(tid("subject-distance")).text_content()
        page.locator("%s [role=radio][data-value='%s']" % (tid(group), value)).click()
        self.wait_text_not(page, before)

    def check_agrees(self, text, metres):
        m = float(metres)
        if m >= 10:
            self.assertRegex(text, r"^Subject about \d+ m$")
            self.assertEqual(text, "Subject about %.0f m" % m)
        else:
            self.assertRegex(text, r"^Subject about \d+\.\d m$")
            self.assertEqual(text, "Subject about %.1f m" % m)

    def test_readout_and_marker_follow_lens_and_framing(self):
        page = self.new_page()
        page.wait_for_function(
            "s => { const e = document.querySelector(s); return e && e.textContent.trim() !== ''; }",
            arg=tid("subject-distance"),
        )
        # start from a known pair: 24 mm, full body (about 2.4 m)
        for group, value in (("lens-group", "24"), ("framing-group", "full-body")):
            opt = page.locator("%s [role=radio][data-value='%s']" % (tid(group), value))
            if opt.get_attribute("aria-checked") != "true":
                self.pick(page, group, value)
        text0, metres0, x0 = self.read(page)
        self.check_agrees(text0, metres0)
        self.assertLess(float(metres0), 10)

        self.pick(page, "lens-group", "85")
        text1, metres1, x1 = self.read(page)
        self.check_agrees(text1, metres1)
        self.assertNotEqual(text1, text0)
        self.assertGreater(float(metres1), float(metres0))
        self.assertGreater(x1, x0 + 1)

        self.pick(page, "framing-group", "wide")
        text2, metres2, x2 = self.read(page)
        self.check_agrees(text2, metres2)
        self.assertGreaterEqual(float(metres2), 10)
        self.assertNotEqual(text2, text1)
        self.assertGreater(x2, x1 + 1)


if __name__ == "__main__":
    unittest.main()
