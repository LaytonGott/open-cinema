"""Browser test of the player labels, ready gate and play toggle."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class PlayerTest(unittest.TestCase):
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
        h.fake.reset_cache()
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

    def test_labels(self):
        page = self.finished_page()
        before = page.locator(tid("label-before"))
        after = page.locator(tid("label-after"))
        before.wait_for(state="visible")
        self.assertEqual(before.text_content(), "Before")
        self.assertEqual(after.text_content(), "After f/2.8")
        slider = page.locator(tid("reapply-slider"))
        slider.focus()
        for _ in range(3):
            slider.press("ArrowRight")
        page.locator(tid("reapply-button")).click()
        page.wait_for_function(
            "s => document.querySelectorAll(s).length === 2", arg=tid("version-chip")
        )
        page.locator(tid("version-chip")).filter(has_text="f/8").click()
        page.wait_for_function(
            "s => document.querySelector(s).textContent === 'After f/8'",
            arg=tid("label-after"),
        )
        self.assertEqual(before.text_content(), "Before")

    def test_ready_gate(self):
        page = self.finished_page()
        page.locator(tid("play-toggle")).wait_for(state="attached")
        # The button is enabled exactly when both videos have readyState >= 2.
        page.wait_for_function(
            "() => { const t = document.querySelector('[data-testid=play-toggle]');"
            " const v = ['before-video', 'after-video'].map("
            "n => document.querySelector('[data-testid=' + n + ']'));"
            " const ready = v.every(x => x.readyState >= 2);"
            " return ready && !t.disabled; }"
        )
        self.assertTrue(page.locator(tid("play-toggle")).is_enabled())

    def test_play_pause_together(self):
        page = self.finished_page()
        self.wait_ready(page)
        toggle = page.locator(tid("play-toggle"))
        paused = (
            "() => ['before-video', 'after-video'].map("
            "n => document.querySelector('[data-testid=' + n + ']').paused)"
        )
        toggle.click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=play-toggle]')"
            ".getAttribute('aria-pressed') === 'true'"
        )
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => document.querySelector('[data-testid=' + n + ']').paused === false)"
        )
        self.assertEqual(page.evaluate(paused), [False, False])
        toggle.click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=play-toggle]')"
            ".getAttribute('aria-pressed') === 'false'"
        )
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => document.querySelector('[data-testid=' + n + ']').paused === true)"
        )
        self.assertEqual(page.evaluate(paused), [True, True])


if __name__ == "__main__":
    unittest.main()
