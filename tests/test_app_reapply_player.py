"""Browser test that the player stays usable while a re-apply runs."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness
from tests.player_pause import pause_players

GENERATION = ("SamplerCustomAdvanced", "VAEDecodeTiled")
DEPTH = ("DA3Inference", "OpenOptics_DepthToMetric")
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

    def wait_src_not(self, page, old):
        page.wait_for_function(
            "([s, old]) => { const e = document.querySelector(s);"
            " return (e.currentSrc || e.src) !== old; }",
            arg=[tid("after-video"), old],
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
            pause_players(page)
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

    def test_chip_switch_does_not_regenerate(self):
        h = self.harness
        fake = h.fake
        page = self.finished_page()
        slider = page.locator(tid("reapply-slider"))
        slider.wait_for(state="visible")
        watched = GENERATION + DEPTH
        before = {c: fake.count(c) for c in watched + ("OpenOptics_DepthOfField",)}
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
        self.assertEqual(
            fake.count("OpenOptics_DepthOfField"), before["OpenOptics_DepthOfField"] + 1
        )
        for c in watched:
            self.assertEqual(fake.count(c), before[c], c)
        chips = page.locator(tid("version-chip"))
        self.assertEqual(chips.nth(1).get_attribute("data-aperture"), "8")
        code, listing = h.get("/api/shots")
        self.assertEqual(code, 200)
        code, record = h.get("/api/shots/%s" % listing["shots"][0]["id"])
        self.assertEqual(code, 200)
        self.assertEqual([v["aperture"] for v in record["versions"]], [2.8, 8])

        counts = {c: fake.count(c) for c in before}
        src = lambda: page.locator(tid("after-video")).evaluate("e => e.currentSrc || e.src")
        label = lambda: page.locator(tid("label-after")).text_content().strip()
        src_f8 = src()
        self.assertEqual(label(), "After f/8")
        chips.nth(0).click()
        page.wait_for_function(
            "s => document.querySelector(s).textContent.trim() === 'After f/2.8'",
            arg=tid("label-after"),
        )
        self.wait_src_not(page, src_f8)
        src_f28 = src()
        self.assertNotEqual(src_f28, src_f8)
        chips.nth(1).click()
        page.wait_for_function(
            "s => document.querySelector(s).textContent.trim() === 'After f/8'",
            arg=tid("label-after"),
        )
        self.wait_src_not(page, src_f28)
        self.assertNotEqual(src(), src_f28)
        for c, n in counts.items():
            self.assertEqual(fake.count(c), n, c)

    def test_failed_reapply_then_retry_counts(self):
        h = self.harness
        fake = h.fake
        message = "Simulated failure"
        page = self.finished_page()
        self.addCleanup(fake.clear_failures)
        slider = page.locator(tid("reapply-slider"))
        slider.wait_for(state="visible")
        optics = "OpenOptics_DepthOfField"
        before = fake.count(optics)
        fake.fail(optics, message)
        slider.focus()
        for _ in range(3):
            slider.press("ArrowRight")
        page.locator(tid("reapply-button")).click()
        page.wait_for_function(
            "([s, t]) => document.querySelector(s) && document.querySelector(s).textContent.includes(t)",
            arg=[tid("reapply-status"), message],
        )
        self.assertEqual(page.locator(tid("version-chip")).count(), 1)
        # The fake fails the node before recording it as executed.
        self.assertEqual(fake.count(optics), before)
        self.wait_ready(page)
        pause_players(page)
        page.locator(tid("play-toggle")).click()
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => document.querySelector('[data-testid=' + n + ']').paused === false)"
        )

        fake.clear_failures()
        page.locator(tid("reapply-button")).click()
        page.wait_for_function(
            "s => document.querySelectorAll(s).length === 2", arg=tid("version-chip")
        )
        self.assertEqual(fake.count(optics), before + 1)


if __name__ == "__main__":
    unittest.main()
