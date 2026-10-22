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

    def test_videos_stay_in_sync(self):
        page = self.finished_page()
        self.wait_ready(page)
        times = (
            "() => ['before-video', 'after-video'].map("
            "n => document.querySelector('[data-testid=' + n + ']').currentTime)"
        )

        def diff():
            a, b = page.evaluate(times)
            return abs(a - b)

        toggle = page.locator(tid("play-toggle"))
        toggle.click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=before-video]').currentTime > 1"
        )
        self.assertLess(diff(), 0.25)

        toggle.click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=before-video]').paused === true"
        )
        target = page.evaluate(
            "() => { const v = document.querySelector('[data-testid=before-video]');"
            " const t = Math.min(0.5, v.duration / 2); v.currentTime = t; return t; }"
        )
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every(n => {"
            " const v = document.querySelector('[data-testid=' + n + ']');"
            " return !v.seeking && Math.abs(v.currentTime - %r) < 0.25; })" % target
        )
        self.assertLess(diff(), 0.25)

        toggle.click()
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => document.querySelector('[data-testid=' + n + ']').paused === false)"
        )
        previous = page.evaluate(times)[0]
        page.wait_for_function(
            "p => document.querySelector('[data-testid=before-video]').currentTime > 0.3"
            " && document.querySelector('[data-testid=before-video]').currentTime > p"
            " || false",
            arg=previous,
            timeout=30000,
        )
        # Let the clip play to its end; currentTime drops below its largest value on the loop.
        page.evaluate(
            "() => { window.__maxT = 0; window.__looped = false;"
            " const v = document.querySelector('[data-testid=before-video]');"
            " setInterval(() => { if (v.currentTime < window.__maxT - 0.5)"
            " window.__looped = true; window.__maxT = Math.max(window.__maxT, v.currentTime); }, 20); }"
        )
        page.wait_for_function("() => window.__looped === true", timeout=30000)
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => document.querySelector('[data-testid=' + n + ']').paused === false)"
        )
        for _ in range(5):
            self.assertLess(diff(), 0.25)
            page.wait_for_timeout(100)

    def test_scrubber(self):
        page = self.finished_page()
        self.wait_ready(page)
        page.evaluate(
            "() => { const s = document.querySelector('[data-testid=scrubber]');"
            " s.value = 500; s.dispatchEvent(new Event('input', {bubbles: true})); }"
        )
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every(n => {"
            " const v = document.querySelector('[data-testid=' + n + ']');"
            " return !v.seeking && Math.abs(v.currentTime - v.duration / 2) < 0.2; })"
        )
        toggle = page.locator(tid("play-toggle"))
        toggle.click()
        page.wait_for_function(
            "() => Number(document.querySelector('[data-testid=scrubber]').value) > 500"
            " || document.querySelector('[data-testid=before-video]').ended",
            timeout=30000,
        )
        toggle.click()
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => document.querySelector('[data-testid=' + n + ']').paused === true)"
        )

    def test_compare_slider_keyboard(self):
        page = self.finished_page()
        slider = page.locator(tid("compare-slider"))
        slider.wait_for(state="attached")
        self.assertEqual(slider.get_attribute("role"), "slider")
        self.assertEqual(slider.get_attribute("aria-label"), "Before and after")
        self.assertEqual(slider.get_attribute("aria-valuemin"), "0")
        self.assertEqual(slider.get_attribute("aria-valuemax"), "100")
        self.assertEqual(slider.get_attribute("aria-valuenow"), "50")

        def expect_value(value):
            page.wait_for_function(
                "v => document.querySelector('[data-testid=compare-slider]')"
                ".getAttribute('aria-valuenow') === v",
                arg=str(value),
            )

        slider.focus()
        slider.press("ArrowRight")
        expect_value(51)
        slider.press("Shift+ArrowLeft")
        expect_value(41)
        slider.press("Home")
        expect_value(0)
        slider.press("End")
        expect_value(100)
        for _ in range(3):
            slider.press("ArrowRight")
        expect_value(100)


if __name__ == "__main__":
    unittest.main()
