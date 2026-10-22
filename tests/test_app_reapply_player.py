"""Browser test that the player stays usable while a re-apply runs."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class ReapplyPlayerTest(unittest.TestCase):
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

    def test_player_visible_and_playable_during_reapply(self):
        h = self.harness
        page = self.finished_page()
        slider = page.locator(tid("reapply-slider"))
        slider.wait_for(state="visible")
        h.fake.hold_at("OpenOptics_DepthOfField")
        try:
            slider.focus()
            for _ in range(3):
                slider.press("ArrowRight")
            page.locator(tid("reapply-button")).click()
            page.wait_for_function(
                "s => document.querySelector(s) && document.querySelector(s).textContent.trim().startsWith('Applying')",
                arg=tid("reapply-status"),
            )
            self.assertEqual(
                page.locator(tid("viewport")).get_attribute("data-state"), "result"
            )
            self.assertTrue(page.locator(tid("player")).is_visible())
            self.wait_ready(page)
            page.locator(tid("play-toggle")).click()
            page.wait_for_function(
                "() => ['before-video', 'after-video'].every("
                "n => document.querySelector('[data-testid=' + n + ']').paused === false)"
            )
        finally:
            h.fake.release()
        page.wait_for_function(
            "s => document.querySelectorAll(s).length === 2", arg=tid("version-chip")
        )
        page.wait_for_function(
            "s => document.querySelector(s).textContent.trim() === 'Applied f/8'",
            arg=tid("reapply-status"),
        )
        chips = page.locator(tid("version-chip"))
        self.assertEqual(chips.nth(1).get_attribute("aria-pressed"), "true")


if __name__ == "__main__":
    unittest.main()
