"""Browser tests that the player survives rapid shot switching and New shot."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class PlayerRobustTest(unittest.TestCase):
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
        return page

    def wait_state(self, page, state):
        page.wait_for_function(
            "([s, st]) => document.querySelector(s) && document.querySelector(s).dataset.state === st",
            arg=[tid("viewport"), state],
        )

    def generate(self, page, text):
        page.locator(tid("shot-description")).fill(text)
        page.locator(tid("generate-button")).click()
        self.wait_state(page, "result")
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.status === 'done'",
            arg=tid("history-item"),
        )

    def test_rapid_switching_ends_on_last_clicked_shot(self):
        self.harness.reset()
        page = self.new_page()
        page.goto(self.harness.url)
        self.generate(page, DESCRIPTION + " One.")
        page.locator(tid("history-new")).click()
        self.wait_state(page, "empty")
        self.generate(page, DESCRIPTION + " Two.")
        page.wait_for_function(
            "s => document.querySelectorAll(s).length === 2 && "
            "[...document.querySelectorAll(s)].every(e => e.dataset.status === 'done')",
            arg=tid("history-item"),
        )
        items = page.locator(tid("history-item"))
        ids = [items.nth(i).get_attribute("data-shot-id") for i in range(2)]
        self.assertNotEqual(ids[0], ids[1])
        last = None
        for n in range(10):
            last = ids[n % 2]
            items.nth(n % 2).click()
        self.wait_state(page, "result")
        for name in ("after-video", "before-video"):
            page.wait_for_function(
                "([s, id]) => { const e = document.querySelector(s);"
                " return !!e && (e.currentSrc || e.src).includes(id); }",
                arg=[tid(name), last],
            )
        page.wait_for_function(
            "() => { const t = document.querySelector('[data-testid=play-toggle]');"
            " return !!t && !t.disabled; }"
        )
        page.locator(tid("play-toggle")).click()
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => document.querySelector('[data-testid=' + n + ']').paused === false)"
        )

    def test_new_shot_empties_viewport_without_player_or_errors(self):
        self.harness.reset()
        page = self.new_page()
        errors = []
        page.on(
            "console",
            lambda m: errors.append(m.text) if m.type == "error" else None,
        )
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(self.harness.url)
        self.generate(page, DESCRIPTION)
        self.assertTrue(page.locator(tid("player")).is_visible())
        page.locator(tid("history-new")).click()
        self.wait_state(page, "empty")
        self.assertEqual(page.locator(tid("player")).count(), 0)
        self.assertEqual(errors, [])

    def test_failed_after_video_shows_alert_and_app_keeps_working(self):
        self.harness.reset()
        page = self.new_page()
        page.route(
            "**/media/*/*",
            lambda route: route.fulfill(
                status=200, content_type="video/webm", body=b"not a video"
            ),
        )
        page.goto(self.harness.url)
        self.generate(page, DESCRIPTION)
        error = page.locator(tid("player-error"))
        error.wait_for(state="visible")
        self.assertEqual(error.get_attribute("role"), "alert")
        self.assertTrue(error.inner_text().strip())
        self.assertEqual(page.locator(tid("history-item")).count(), 1)
        self.assertTrue(page.locator(tid("history-item")).first.is_enabled())
        page.locator(tid("history-new")).click()
        self.wait_state(page, "empty")


if __name__ == "__main__":
    unittest.main()
