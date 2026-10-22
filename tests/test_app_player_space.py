"""Browser test of the Space key on the focused player."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."

PAUSED = (
    "() => ['before-video', 'after-video'].map("
    "n => document.querySelector('[data-testid=' + n + ']').paused)"
)


def tid(name):
    return "[data-testid=%s]" % name


class PlayerSpaceTest(unittest.TestCase):
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

    def finished_page(self):
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
        return page

    def wait_ready(self, page):
        page.wait_for_function(
            "() => { const t = document.querySelector('[data-testid=play-toggle]');"
            " return !!t && !t.disabled; }"
        )

    def wait_paused(self, page, paused, pressed):
        page.wait_for_function(
            "([p, a]) => ['before-video', 'after-video'].every("
            "n => document.querySelector('[data-testid=' + n + ']').paused === p)"
            " && document.querySelector('[data-testid=play-toggle]')"
            ".getAttribute('aria-pressed') === a",
            arg=[paused, pressed],
        )

    def test_space_toggles(self):
        page = self.finished_page()
        self.wait_ready(page)
        scroll = page.evaluate("() => window.scrollY")
        page.focus(tid("player"))
        page.keyboard.press("Space")
        self.wait_paused(page, False, "true")
        self.assertEqual(page.evaluate(PAUSED), [False, False])
        page.keyboard.press("Space")
        self.wait_paused(page, True, "false")
        self.assertEqual(page.evaluate(PAUSED), [True, True])
        self.assertEqual(page.evaluate("() => window.scrollY"), scroll)

    def test_space_in_description_ignored(self):
        page = self.finished_page()
        self.wait_ready(page)
        before = page.evaluate(PAUSED)
        field = page.locator(tid("shot-description"))
        field.focus()
        page.keyboard.press("End")
        value = field.input_value()
        page.keyboard.press("Space")
        page.wait_for_function(
            "v => document.querySelector('[data-testid=shot-description]').value === v",
            arg=value + " ",
        )
        self.assertEqual(page.evaluate(PAUSED), before)

    def test_player_focus_outline(self):
        page = self.finished_page()
        self.wait_ready(page)
        page.focus(tid("player"))
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        width = page.evaluate(
            "() => parseFloat(getComputedStyle("
            "document.querySelector('[data-testid=player]')).outlineWidth)"
        )
        self.assertGreater(width, 0)


if __name__ == "__main__":
    unittest.main()
