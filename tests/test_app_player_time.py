"""Browser test of the player time readout."""
import re
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness
from tests.player_pause import pause_players

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."
READOUT = "^\\d+:\\d\\d / \\d+:\\d\\d$"
GET_TEXT = "() => document.querySelector('[data-testid=time-readout]').textContent"


def tid(name):
    return "[data-testid=%s]" % name


def seconds(part):
    minutes, secs = part.strip().split(":")
    return int(minutes) * 60 + int(secs)


class PlayerTimeTest(unittest.TestCase):
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

    def test_readout_format(self):
        page = self.finished_page()
        readout = page.locator(tid("time-readout"))
        readout.wait_for(state="attached")
        text = readout.text_content()
        self.assertRegex(text, READOUT)
        self.assertNotIn("NaN", text)

    def test_readout_advances_on_play(self):
        page = self.finished_page()
        self.wait_ready(page)
        pause_players(page)
        toggle = page.locator(tid("play-toggle"))
        toggle.click()
        try:
            page.wait_for_function(
                "() => document.querySelector('[data-testid=time-readout]')"
                ".textContent.split(' / ')[0] !== '0:00'",
                timeout=30000,
            )
        finally:
            toggle.click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=before-video]').paused === true"
        )
        text = page.evaluate(GET_TEXT)
        self.assertRegex(text, READOUT)
        self.assertNotIn("NaN", text)

    def test_readout_follows_scrubber(self):
        page = self.finished_page()
        self.wait_ready(page)
        page.evaluate(
            "() => { const s = document.querySelector('[data-testid=scrubber]');"
            " s.value = 500; s.dispatchEvent(new Event('input', {bubbles: true})); }"
        )
        page.wait_for_function(
            "() => document.querySelector('[data-testid=time-readout]')"
            ".textContent.split(' / ')[0] !== '0:00'"
        )
        # Wait until the first part is within a second of half the duration.
        page.wait_for_function(
            "() => { const p = document.querySelector('[data-testid=time-readout]')"
            ".textContent.split(' / ').map(x => { const m = x.split(':');"
            " return Number(m[0]) * 60 + Number(m[1]); });"
            " return Math.abs(p[0] - p[1] / 2) <= 1; }"
        )
        text = page.evaluate(GET_TEXT)
        self.assertRegex(text, READOUT)
        first, second = (seconds(p) for p in text.split(" / "))
        self.assertLessEqual(abs(first - second / 2), 1)


if __name__ == "__main__":
    unittest.main()
