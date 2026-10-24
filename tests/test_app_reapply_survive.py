"""Browser test that a running re-apply survives a shot switch and a page reload."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."
OPTICS = "OpenOptics_DepthOfField"


def tid(name):
    return "[data-testid=%s]" % name


def item(shot_id):
    return "[data-testid=history-item][data-shot-id='%s']" % shot_id


class ReapplySurviveTest(unittest.TestCase):
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

    def two_shots(self):
        """Return (page, id_a, id_b) with shot A generated first and B second."""
        self.harness.reset()
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)
        ids = []
        for count in (1, 2):
            page.locator(tid("shot-description")).fill(DESCRIPTION)
            page.locator(tid("generate-button")).click()
            page.wait_for_function(
                "n => document.querySelectorAll('[data-testid=history-item]').length === n"
                " && document.querySelector('[data-testid=viewport]').dataset.state === 'result'",
                arg=count,
            )
            ids.append(page.locator(tid("history-item")).first.get_attribute("data-shot-id"))
        id_b, id_a = ids
        self.assertNotEqual(id_a, id_b)
        return page, id_a, id_b

    def start_reapply(self, page):
        slider = page.locator(tid("reapply-slider"))
        slider.wait_for(state="visible")
        slider.focus()
        for _ in range(3):
            slider.press("ArrowRight")
        page.locator(tid("reapply-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s).textContent.trim() === 'Applying f/8 ...'",
            arg=tid("reapply-status"),
        )

    def check_running(self, page):
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )
        page.wait_for_function(
            "s => document.querySelector(s).textContent.trim() === 'Applying f/8 ...'",
            arg=tid("reapply-status"),
        )
        self.assertTrue(page.locator(tid("reapply-button")).is_disabled())
        page.wait_for_function(
            "() => { const t = document.querySelector('[data-testid=play-toggle]');"
            " return !!t && !t.disabled; }"
        )

    def check_finished(self, page):
        page.wait_for_function(
            "s => document.querySelectorAll(s).length === 2", arg=tid("version-chip")
        )
        page.wait_for_function(
            "s => document.querySelector(s).textContent.trim() === 'Applied f/8'",
            arg=tid("reapply-status"),
        )

    def test_reapply_survives_shot_switch(self):
        fake = self.harness.fake
        page, id_a, id_b = self.two_shots()
        page.locator(item(id_a)).click()
        fake.hold_at(OPTICS)
        try:
            self.start_reapply(page)
            page.locator(item(id_b)).click()
            page.wait_for_function(
                "s => !document.querySelector(s).textContent.includes('Applying')",
                arg=tid("reapply-status"),
            )
            page.locator(item(id_a)).click()
            self.check_running(page)
            page.locator(tid("play-toggle")).click()
            page.wait_for_function(
                "() => ['before-video', 'after-video'].every("
                "n => document.querySelector('[data-testid=' + n + ']').paused === false)"
            )
        finally:
            fake.release()
        self.check_finished(page)

    def test_reapply_survives_reload(self):
        fake = self.harness.fake
        page, id_a, id_b = self.two_shots()
        page.locator(item(id_a)).click()
        fake.hold_at(OPTICS)
        try:
            self.start_reapply(page)
            page.reload()
            self.check_running(page)
        finally:
            fake.release()
        self.check_finished(page)


if __name__ == "__main__":
    unittest.main()
