"""Browser test of selecting history shots in the player and reloading."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class PlayerHistoryTest(unittest.TestCase):
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

    def make_shot(self, page, count):
        self.harness.fake.reset_cache()
        page.locator(tid("shot-description")).fill(DESCRIPTION)
        page.locator(tid("generate-button")).click()
        page.wait_for_function(
            "n => document.querySelectorAll('[data-testid=history-item]').length === n"
            " && document.querySelector('[data-testid=viewport]').dataset.state === 'result'",
            arg=count,
        )
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => !!document.querySelector('[data-testid=' + n + ']').getAttribute('src'))"
        )

    def srcs(self, page):
        return page.evaluate(
            "() => ['before-video', 'after-video'].map("
            "n => document.querySelector('[data-testid=' + n + ']').getAttribute('src'))"
        )

    def wait_srcs(self, page, expected):
        page.wait_for_function(
            "e => ['before-video', 'after-video'].every((n, i) =>"
            " document.querySelector('[data-testid=' + n + ']').getAttribute('src') === e[i])",
            arg=expected,
        )
        page.wait_for_function(
            "() => { const t = document.querySelector('[data-testid=play-toggle]');"
            " return !!t && !t.disabled; }"
        )

    def select(self, page, shot_id):
        page.locator("[data-testid=history-item][data-shot-id='%s']" % shot_id).click()

    def test_history_selection_loads_videos(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)

        self.make_shot(page, 1)
        older_id = page.locator(tid("history-item")).first.get_attribute("data-shot-id")
        older = self.srcs(page)
        self.make_shot(page, 2)
        newer_id = page.locator(tid("history-item")).first.get_attribute("data-shot-id")
        # The after video is swapped in once the new version has loaded.
        page.wait_for_function(
            "old => document.querySelector('[data-testid=after-video]').getAttribute('src') !== old",
            arg=older[1],
        )
        newer = self.srcs(page)
        self.assertNotEqual(older_id, newer_id)
        self.assertTrue(all(older) and all(newer))
        self.assertNotEqual(older[0], newer[0])
        self.assertNotEqual(older[1], newer[1])

        self.select(page, older_id)
        self.wait_srcs(page, older)
        self.select(page, newer_id)
        self.wait_srcs(page, newer)
        self.select(page, older_id)
        self.wait_srcs(page, older)

        page.reload()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )
        page.locator(tid("player")).wait_for(state="attached")
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => !!document.querySelector('[data-testid=' + n + ']').getAttribute('src'))"
        )
        # A reload shows the latest shot again.
        page.wait_for_function(
            "id => { const e = document.querySelector('[data-testid=history-item][aria-current=true]');"
            " return !!e && e.dataset.shotId === id; }",
            arg=newer_id,
        )
        self.wait_srcs(page, newer)

    def wait_chips(self, page, count, label):
        page.wait_for_function(
            "([n, t]) => document.querySelectorAll('[data-testid=version-chip]').length === n"
            " && document.querySelector('[data-testid=label-after]').textContent === t",
            arg=[count, label],
        )

    def chip_apertures(self, page):
        return page.evaluate(
            "() => [...document.querySelectorAll('[data-testid=version-chip]')]"
            ".map(c => parseFloat(c.dataset.aperture))"
        )

    def test_selection_shows_chips_and_aperture(self):
        self.harness.reset()
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)

        self.make_shot(page, 1)
        older_id = page.locator(tid("history-item")).first.get_attribute("data-shot-id")
        slider = page.locator(tid("reapply-slider"))
        slider.wait_for(state="visible")
        slider.focus()
        for _ in range(3):
            slider.press("ArrowRight")
        page.locator(tid("reapply-button")).click()
        self.wait_chips(page, 2, "After f/8")

        self.make_shot(page, 2)
        newer_id = page.locator(tid("history-item")).first.get_attribute("data-shot-id")
        self.wait_chips(page, 1, "After f/2.8")
        self.assertEqual(self.chip_apertures(page), [2.8])

        self.select(page, older_id)
        self.wait_chips(page, 2, "After f/8")
        self.assertEqual(self.chip_apertures(page), [2.8, 8.0])
        self.select(page, newer_id)
        self.wait_chips(page, 1, "After f/2.8")

        page.reload()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )
        self.wait_chips(page, 1, "After f/2.8")


if __name__ == "__main__":
    unittest.main()
