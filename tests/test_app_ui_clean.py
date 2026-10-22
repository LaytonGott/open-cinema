"""Browser test that walking every viewport state logs no console errors, failed requests or foreign hosts."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
BANNER = "[data-testid=comfy-banner]"
RETRY = "[data-testid=comfy-retry]"
VIEWPORT = "[data-testid=viewport]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


class CleanPageTest(unittest.TestCase):
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

    def setUp(self):
        h = self.harness
        h.fake.clear_failures()
        h.fake.release()
        deadline = time.time() + 30
        while time.time() < deadline:
            code, body = h.get("/api/shots")
            if code == 200 and all(s["status"] in TERMINAL for s in body["shots"]):
                break
            time.sleep(0.1)
        else:
            raise AssertionError("a shot was still active")
        h.reset()
        self.addCleanup(h.fake.clear_failures)
        self.addCleanup(h.fake.release)

    def wait_state(self, state):
        self.page.wait_for_function(
            "([s, v]) => document.querySelector(s) && document.querySelector(s).dataset.state === v",
            arg=[VIEWPORT, state],
        )

    def wait_status(self, state):
        self.page.wait_for_function(
            "([s, v]) => document.querySelector(s) && document.querySelector(s).dataset.state === v",
            arg=[STATUS, state],
        )

    def generate(self):
        page = self.page
        page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
        page.locator("[data-testid=generate-button]").click()

    def new_shot(self):
        self.page.locator("[data-testid=history-new]").click()
        self.wait_state("empty")

    def test_no_errors_across_states(self):
        h = self.harness
        fake = h.fake
        page = self.page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        errors, failed, urls = [], [], []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("requestfailed", lambda r: failed.append(r.url))
        page.on("request", lambda r: urls.append(r.url))

        page.goto(h.url)
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )
        self.new_shot()

        fake.hold_at("SamplerCustomAdvanced")
        try:
            self.generate()
            self.wait_state("working")
        finally:
            fake.release()
        self.wait_state("result")

        self.new_shot()
        fake.fail("SamplerCustomAdvanced", "boom")
        self.generate()
        self.wait_state("failed")
        fake.clear_failures()

        self.new_shot()
        fake.hold_at("SamplerCustomAdvanced")
        try:
            self.generate()
            self.wait_state("working")
            cancel = page.locator("[data-testid=cancel-button]")
            cancel.wait_for(state="visible")
            cancel.click()
            self.wait_state("cancelled")
        finally:
            fake.release()

        page.reload()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state !== 'empty'", arg=VIEWPORT
        )

        self.assertEqual(errors, [])
        self.assertEqual(failed, [])
        self.assertTrue(urls)
        foreign = [u for u in urls if not u.startswith(h.url)]
        self.assertEqual(foreign, [])

    def test_no_errors_while_comfy_is_down(self):
        h = self.harness
        fake = h.fake
        self.addCleanup(lambda: fake._thread is None and fake.start())
        page = self.page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        errors, failed, urls = [], [], []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("requestfailed", lambda r: failed.append(r.url))
        page.on("request", lambda r: urls.append(r.url))

        page.goto(h.url)
        self.wait_status("ok")
        fake.stop()
        try:
            page.dispatch_event(RETRY, "click")
            self.wait_status("down")
            page.locator(BANNER).wait_for(state="visible")
        finally:
            if fake._thread is None:
                fake.start()
        page.click(RETRY)
        self.wait_status("ok")
        page.locator(BANNER).wait_for(state="hidden")

        self.assertEqual(errors, [])
        self.assertEqual(failed, [])
        self.assertTrue(urls)
        foreign = [u for u in urls if not u.startswith(h.url)]
        self.assertEqual(foreign, [])


if __name__ == "__main__":
    unittest.main()
