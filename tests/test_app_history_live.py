"""Browser test of history statuses staying live while an older shot is selected."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class HistoryLiveTest(unittest.TestCase):
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

    def generate(self, page):
        self.harness.fake.reset_cache()
        page.locator(tid("shot-description")).fill(DESCRIPTION)
        page.locator(tid("generate-button")).click()

    def test_live_status_while_older_selected(self):
        self.harness.reset()
        fake = self.harness.fake
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)

        self.generate(page)
        page.wait_for_function(
            "() => document.querySelectorAll('[data-testid=history-item]').length === 1"
            " && document.querySelector('[data-testid=viewport]').dataset.state === 'result'"
        )
        page.wait_for_function(
            "() => !!document.querySelector('[data-testid=before-video]').getAttribute('src')"
        )
        older = page.locator(tid("history-item")).first
        older_id = older.get_attribute("data-shot-id")
        older_src = page.locator(tid("before-video")).get_attribute("src")

        fake.hold_at("SamplerCustomAdvanced")
        try:
            self.generate(page)
            page.wait_for_function(
                "() => document.querySelectorAll('[data-testid=history-item]').length === 2"
            )
            running = page.locator(tid("history-item")).first
            running_id = running.get_attribute("data-shot-id")
            self.assertNotEqual(running_id, older_id)
            sel = "[data-testid=history-item][data-shot-id='%s']" % running_id
            page.wait_for_function(
                "s => ['queued', 'generating', 'optics'].includes(document.querySelector(s).dataset.status)",
                arg=sel,
            )

            page.locator("[data-testid=history-item][data-shot-id='%s']" % older_id).click()
            page.locator(tid("player")).wait_for(state="visible")
            page.wait_for_function(
                "src => document.querySelector('[data-testid=before-video]').getAttribute('src') === src",
                arg=older_src,
            )
            self.assertNotEqual(page.locator(sel).get_attribute("data-status"), "done")
        finally:
            fake.release()

        page.wait_for_function(
            "s => document.querySelector(s).dataset.status === 'done'", arg=sel
        )
        self.assertEqual(page.locator(tid("before-video")).get_attribute("src"), older_src)

    def test_follow_running_shot_to_result(self):
        self.harness.reset()
        fake = self.harness.fake
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)

        self.generate(page)
        page.wait_for_function(
            "() => document.querySelectorAll('[data-testid=history-item]').length === 1"
            " && document.querySelector('[data-testid=viewport]').dataset.state === 'result'"
        )

        fake.hold_at("SamplerCustomAdvanced")
        try:
            self.generate(page)
            page.wait_for_function(
                "() => document.querySelectorAll('[data-testid=history-item]').length === 2"
            )
            running_id = page.locator(tid("history-item")).first.get_attribute("data-shot-id")
            sel = "[data-testid=history-item][data-shot-id='%s']" % running_id
            page.wait_for_function(
                "s => ['queued', 'generating', 'optics'].includes(document.querySelector(s).dataset.status)",
                arg=sel,
            )

            page.locator(sel).click()
            page.wait_for_function(
                "() => document.querySelector('[data-testid=viewport]').dataset.state === 'working'"
            )
        finally:
            fake.release()

        page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'result'"
        )

    def test_reapply_isolated_between_shots(self):
        self.harness.reset()
        fake = self.harness.fake
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)

        ids = []
        for count in (1, 2):
            self.generate(page)
            page.wait_for_function(
                "n => document.querySelectorAll('[data-testid=history-item]').length === n"
                " && document.querySelector('[data-testid=viewport]').dataset.state === 'result'",
                arg=count,
            )
            ids.append(page.locator(tid("history-item")).first.get_attribute("data-shot-id"))
        id_b, id_a = ids
        self.assertNotEqual(id_a, id_b)

        button = page.locator(tid("reapply-button"))
        slider = page.locator(tid("reapply-slider"))
        status = page.locator(tid("reapply-status"))

        def set_slider(index):
            slider.evaluate(
                "(el, i) => { el.value = String(i); el.dispatchEvent(new Event('input', {bubbles: true})); }",
                index,
            )

        page.locator("[data-testid=history-item][data-shot-id='%s']" % id_a).click()
        button.wait_for(state="visible")
        fake.hold_at("OpenOptics_DepthOfField")
        try:
            set_slider(5)
            button.click()
            page.wait_for_function(
                "s => document.querySelector(s).textContent.includes('Applying')",
                arg=tid("reapply-status"),
            )

            page.locator("[data-testid=history-item][data-shot-id='%s']" % id_b).click()
            page.wait_for_function(
                "s => !document.querySelector(s).textContent.includes('Applying')",
                arg=tid("reapply-status"),
            )
            set_slider(5)
            self.assertTrue(button.is_enabled())
            self.assertNotIn("Applying", status.text_content())
            self.assertTrue(page.locator(tid("player")).is_visible())
        finally:
            fake.release()

    def test_failed_shot_shows_state(self):
        self.harness.reset()
        fake = self.harness.fake
        self.addCleanup(fake.clear_failures)
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)

        fake.fail("SamplerCustomAdvanced", "Out of memory in sampler")
        self.generate(page)
        page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'failed'"
        )
        failed_id = page.locator(tid("history-item")).first.get_attribute("data-shot-id")
        fail_sel = "[data-testid=history-item][data-shot-id='%s']" % failed_id
        self.assertEqual(page.locator(fail_sel).get_attribute("data-status"), "failed")
        fake.clear_failures()

        self.generate(page)
        page.wait_for_function(
            "() => document.querySelectorAll('[data-testid=history-item]').length === 2"
            " && document.querySelector('[data-testid=viewport]').dataset.state === 'result'"
        )
        self.assertNotEqual(
            page.locator(tid("history-item")).first.get_attribute("data-shot-id"), failed_id
        )

        page.locator(fail_sel).click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'failed'"
        )


if __name__ == "__main__":
    unittest.main()
