"""Browser test that submitting the form shows the working state and sends a prompt built from the form."""
import json
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
VIEWPORT = "[data-testid=viewport]"
PANEL = "[data-testid=status-panel]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


class RunTest(unittest.TestCase):
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
        h.fake.release()
        deadline = time.time() + 30
        while time.time() < deadline:
            code, body = h.get("/api/shots")
            if code == 200 and all(s["status"] in TERMINAL for s in body["shots"]):
                break
            time.sleep(0.1)
        else:
            raise AssertionError("a shot was still active")
        h.fake.reset_cache()
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(h.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def test_generate_shows_working_and_prompt_from_form(self):
        h, fake, page = self.harness, self.harness.fake, self.page
        fake.hold_at("SamplerCustomAdvanced")
        shot_id = None
        try:
            page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
            page.locator("[data-testid=camera-group] [data-value=dolly-in]").click()
            page.locator("[data-testid=generate-button]").click()
            page.wait_for_function(
                "s => document.querySelector(s).dataset.state === 'working'", arg=VIEWPORT
            )
            page.wait_for_function(
                "s => document.querySelector(s).dataset.status === 'generating'", arg=PANEL
            )
            deadline = time.time() + 15
            while not fake.prompts and time.time() < deadline:
                time.sleep(0.05)
            code, body = h.get("/api/shots")
            self.assertEqual(code, 200)
            shot_id = body["shots"][0]["id"]
            prompts = json.dumps(fake.prompts)
            self.assertIn(DESCRIPTION, prompts)
            self.assertIn("Slow dolly-in toward the subject", prompts)
            self.assertIn("Full-body shot", prompts)
            self.assertIn("50 mm lens look", prompts)
        finally:
            fake.release()
        if shot_id is not None:
            h.wait_for_shot(shot_id, "done")

    def test_cancel_held_shot(self):
        fake, page = self.harness.fake, self.page
        fake.hold_at("SamplerCustomAdvanced")
        try:
            page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
            page.locator("[data-testid=generate-button]").click()
            page.wait_for_function(
                "s => document.querySelector(s).dataset.state === 'working'", arg=VIEWPORT
            )
            page.locator("[data-testid=cancel-button]").click()
            page.wait_for_function(
                "s => document.querySelector(s).dataset.state === 'cancelled'", arg=VIEWPORT
            )
        finally:
            fake.release()
        self.assertEqual(page.locator("[data-testid=status-label]").inner_text().strip(), "Cancelled.")
        self.assertEqual(page.locator("[data-testid=retry-button]").inner_text().strip(), "Try again")

    def fail_then_retry(self, node, message, label):
        fake, page = self.harness.fake, self.page
        self.addCleanup(fake.clear_failures)
        fake.fail(node, message)
        page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
        page.locator("[data-testid=generate-button]").click()
        page.wait_for_function(
            "s => document.querySelector(s).dataset.state === 'failed'", arg=VIEWPORT
        )
        self.assertIn(message, page.locator("[data-testid=error-message]").inner_text())
        self.assertEqual(page.locator("[data-testid=retry-button]").inner_text().strip(), label)
        fake.clear_failures()
        page.locator("[data-testid=retry-button]").click()
        page.wait_for_function(
            "s => document.querySelector(s).dataset.state === 'result'", arg=VIEWPORT
        )

    def test_optics_failure_retry_optics(self):
        self.fail_then_retry("OpenOptics_DepthOfField", "Out of memory in Depth of Field", "Retry optics")

    def test_generate_failure_try_again(self):
        self.fail_then_retry("SamplerCustomAdvanced", "Out of memory in sampler", "Try again")

    def test_run_comfy_down_then_recovers(self):
        fake, page = self.harness.fake, self.page
        fake.stop()
        restored = False

        def restore():
            if not restored:
                fake.start()

        self.addCleanup(restore)
        page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
        page.locator("[data-testid=generate-button]").click()
        page.wait_for_function(
            "s => document.querySelector(s).dataset.state === 'down'", arg=STATUS
        )
        error = page.locator("[data-testid=submit-error]")
        self.assertTrue(error.is_visible())
        self.assertTrue(error.inner_text().strip())
        fake.start()
        restored = True
        page.locator("[data-testid=comfy-retry]").click()
        page.wait_for_function(
            "s => document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )


if __name__ == "__main__":
    unittest.main()
