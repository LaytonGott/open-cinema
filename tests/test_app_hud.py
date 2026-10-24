"""Browser test that the HUD follows the shown version and the selected shot."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


def squash(text):
    """Lower case with only letters, digits, '/' and '.' kept."""
    return "".join(c for c in text.lower() if c.isalnum() or c in "/.")


class HudTest(unittest.TestCase):
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

    def wait_result(self, page):
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )

    def generate(self, page):
        page.locator(tid("shot-description")).fill(DESCRIPTION)
        page.locator(tid("generate-button")).click()
        self.wait_result(page)

    def wait_hud(self, page, *parts):
        page.wait_for_function(
            "([s, parts]) => { const e = document.querySelector(s); if (!e) return false;"
            " const t = e.textContent.toLowerCase().replace(/[^a-z0-9/.]/g, '');"
            " return parts.every(p => t.includes(p)); }",
            arg=[tid("hud"), [squash(p) for p in parts]],
        )

    def test_hud_follows_version_chips(self):
        self.harness.reset()
        page = self.new_page()
        self.generate(page)
        slider = page.locator(tid("reapply-slider"))
        slider.wait_for(state="visible")
        slider.focus()
        for _ in range(3):
            slider.press("ArrowRight")
        page.locator(tid("reapply-button")).click()
        page.wait_for_function(
            "s => document.querySelectorAll(s).length === 2", arg=tid("version-chip")
        )
        chips = page.locator(tid("version-chip"))
        chips.nth(0).click()
        self.wait_hud(page, "f/2.8")
        self.assertIn("f/2.8", page.locator(tid("hud")).text_content())
        chips.nth(1).click()
        self.wait_hud(page, "f/8")
        self.assertIn("f/8", page.locator(tid("hud")).text_content())

    def test_hud_follows_selected_shot(self):
        h = self.harness
        h.reset()
        page = self.new_page()
        shots = [("24", "close-up"), ("85", "wide")]
        for lens, framing in shots:
            h.fake.reset_cache()
            page.locator("%s [data-value='%s']" % (tid("lens-group"), lens)).click()
            page.locator("%s [data-value='%s']" % (tid("framing-group"), framing)).click()
            self.generate(page)
        page.wait_for_function(
            "s => document.querySelectorAll(s).length === 2", arg=tid("history-item")
        )
        items = page.locator(tid("history-item"))
        # Newest first: item 0 is the second shot.
        for index, (lens, framing) in zip((1, 0), shots):
            items.nth(index).click()
            self.wait_result(page)
            self.wait_hud(page, "%s mm" % lens, framing)
            text = squash(page.locator(tid("hud")).text_content())
            self.assertIn(lens + "mm", text)
            self.assertIn(squash(framing), text)


if __name__ == "__main__":
    unittest.main()
