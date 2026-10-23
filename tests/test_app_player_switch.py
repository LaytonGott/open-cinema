"""Browser test that switching version keeps the player's time and compare position."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class PlayerSwitchTest(unittest.TestCase):
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

    def two_version_page(self):
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
        slider = page.locator(tid("reapply-slider"))
        slider.wait_for(state="visible")
        slider.focus()
        for _ in range(3):
            slider.press("ArrowRight")
        page.locator(tid("reapply-button")).click()
        page.wait_for_function(
            "s => document.querySelectorAll(s).length === 2", arg=tid("version-chip")
        )
        page.wait_for_function(
            "s => document.querySelector(s).textContent.trim() === 'Applied f/8'",
            arg=tid("reapply-status"),
        )
        page.wait_for_function(
            "() => { const t = document.querySelector('[data-testid=play-toggle]');"
            " return !!t && !t.disabled; }"
        )
        return page

    def test_paused_switch_keeps_time(self):
        page = self.two_version_page()
        toggle = page.locator(tid("play-toggle"))
        if not page.evaluate(
            "() => document.querySelector('[data-testid=before-video]').paused"
        ):
            toggle.click()
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => document.querySelector('[data-testid=' + n + ']').paused === true)"
        )
        target = page.evaluate(
            "() => { const v = document.querySelector('[data-testid=before-video]');"
            " const t = Math.min(2, v.duration / 2); v.currentTime = t; return t; }"
        )
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every(n => {"
            " const v = document.querySelector('[data-testid=' + n + ']');"
            " return !v.seeking && Math.abs(v.currentTime - %r) < 0.25; })" % target
        )
        slider = page.locator(tid("compare-slider"))
        slider.focus()
        slider.press("Home")
        for _ in range(3):
            slider.press("Shift+ArrowRight")
        page.wait_for_function(
            "() => document.querySelector('[data-testid=compare-slider]')"
            ".getAttribute('aria-valuenow') === '30'"
        )

        old = page.locator(tid("after-video")).evaluate("e => e.currentSrc || e.src")
        chips = page.locator(tid("version-chip"))
        other = 0 if chips.nth(1).get_attribute("aria-pressed") == "true" else 1
        chips.nth(other).click()
        page.wait_for_function(
            "old => { const e = document.querySelector('[data-testid=after-video]');"
            " return (e.currentSrc || e.src) !== old && e.readyState >= 2; }",
            arg=old,
        )

        state = page.evaluate(
            "() => { const g = n => document.querySelector('[data-testid=' + n + ']');"
            " return { b: g('before-video').currentTime, a: g('after-video').currentTime,"
            " bp: g('before-video').paused, ap: g('after-video').paused }; }"
        )
        self.assertAlmostEqual(state["a"], state["b"], delta=0.25)
        self.assertAlmostEqual(state["a"], target, delta=0.25)
        self.assertTrue(state["bp"])
        self.assertTrue(state["ap"])
        self.assertEqual(slider.get_attribute("aria-valuenow"), "30")

    def test_reapply_keeps_time_and_pause(self):
        page = self.two_version_page()
        if not page.evaluate(
            "() => document.querySelector('[data-testid=before-video]').paused"
        ):
            page.locator(tid("play-toggle")).click()
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => document.querySelector('[data-testid=' + n + ']').paused === true)"
        )
        target = page.evaluate(
            "() => { const v = document.querySelector('[data-testid=before-video]');"
            " const t = Math.min(2, v.duration / 2); v.currentTime = t; return t; }"
        )
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every(n => {"
            " const v = document.querySelector('[data-testid=' + n + ']');"
            " return !v.seeking && Math.abs(v.currentTime - %r) < 0.25; })" % target
        )

        slider = page.locator(tid("reapply-slider"))
        slider.focus()
        slider.press("ArrowRight")
        page.locator(tid("reapply-button")).click()
        page.wait_for_function(
            "s => document.querySelectorAll(s).length === 3", arg=tid("version-chip")
        )
        page.wait_for_function(
            "() => { const t = document.querySelector('[data-testid=reapply-status]')"
            ".textContent.trim(); return t.startsWith('Applied f/') && t !== 'Applied f/8'; }"
        )
        page.wait_for_function(
            "() => { const e = document.querySelector('[data-testid=after-video]');"
            " return e.readyState >= 2 && !e.seeking; }"
        )

        state = page.evaluate(
            "() => { const g = n => document.querySelector('[data-testid=' + n + ']');"
            " return { b: g('before-video').currentTime, a: g('after-video').currentTime,"
            " bp: g('before-video').paused, ap: g('after-video').paused }; }"
        )
        self.assertAlmostEqual(state["a"], target, delta=0.25)
        self.assertTrue(state["bp"])
        self.assertTrue(state["ap"])

    def test_playing_switch_keeps_playing(self):
        page = self.two_version_page()
        if page.evaluate(
            "() => document.querySelector('[data-testid=before-video]').paused"
        ):
            page.locator(tid("play-toggle")).click()
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every(n => {"
            " const v = document.querySelector('[data-testid=' + n + ']');"
            " return !v.paused && v.currentTime > 0.1; })"
        )

        old = page.locator(tid("after-video")).evaluate("e => e.currentSrc || e.src")
        chips = page.locator(tid("version-chip"))
        other = 0 if chips.nth(1).get_attribute("aria-pressed") == "true" else 1
        chips.nth(other).click()
        page.wait_for_function(
            "old => { const e = document.querySelector('[data-testid=after-video]');"
            " return (e.currentSrc || e.src) !== old && e.readyState >= 2; }",
            arg=old,
        )
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => !document.querySelector('[data-testid=' + n + ']').paused)"
        )

        state = page.evaluate(
            "() => { const g = n => document.querySelector('[data-testid=' + n + ']');"
            " return { b: g('before-video').currentTime, a: g('after-video').currentTime,"
            " bp: g('before-video').paused, ap: g('after-video').paused }; }"
        )
        self.assertFalse(state["bp"])
        self.assertFalse(state["ap"])
        self.assertAlmostEqual(state["a"], state["b"], delta=0.25)


if __name__ == "__main__":
    unittest.main()
