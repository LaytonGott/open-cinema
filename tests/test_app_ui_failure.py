"""Browser test that a failed optics stage shows an error and Retry optics reuses the generated image."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
VIEWPORT = "[data-testid=viewport]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn."
MESSAGE = "Out of memory in Depth of Field"


class FailureTest(unittest.TestCase):
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
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(h.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def wait_state(self, testid, state):
        self.page.wait_for_function(
            "([s, v]) => document.querySelector(s) && document.querySelector(s).dataset.state === v",
            arg=[f"[data-testid={testid}]", state],
        )

    def test_retry_optics(self):
        fake, page = self.harness.fake, self.page
        fake.fail("OpenOptics_DepthOfField", MESSAGE)
        page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
        page.locator("[data-testid=generate-button]").click()
        self.wait_state("viewport", "failed")
        error = page.locator("[data-testid=error-message]")
        self.assertEqual(error.get_attribute("role"), "alert")
        text = error.inner_text()
        self.assertIn(MESSAGE, text)
        self.assertIn("OpenOptics_DepthOfField", text)
        self.assertEqual(page.locator("[data-testid=stage-generate]").get_attribute("data-state"), "done")
        self.assertEqual(page.locator("[data-testid=stage-optics]").get_attribute("data-state"), "failed")
        self.assertEqual(page.locator("[data-testid=retry-button]").inner_text().strip(), "Retry optics")
        n = fake.count("SamplerCustomAdvanced")
        fake.clear_failures()
        page.locator("[data-testid=retry-button]").click()
        self.wait_state("viewport", "result")
        self.assertEqual(fake.count("SamplerCustomAdvanced"), n)

    def test_try_again(self):
        fake, page = self.harness.fake, self.page
        fake.fail("SamplerCustomAdvanced", "Out of memory in sampler")
        page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
        page.locator("[data-testid=generate-button]").click()
        self.wait_state("viewport", "failed")
        self.assertIn("Out of memory in sampler", page.locator("[data-testid=error-message]").inner_text())
        self.assertEqual(page.locator("[data-testid=stage-generate]").get_attribute("data-state"), "failed")
        self.assertEqual(page.locator("[data-testid=retry-button]").inner_text().strip(), "Try again")
        items = page.locator("[data-testid=history-item]")
        before = items.count()  # the app is shared, so earlier tests' shots are also listed
        self.assertEqual(items.first.get_attribute("data-status"), "failed")
        failed_id = items.first.get_attribute("data-shot-id")
        fake.clear_failures()
        page.locator("[data-testid=retry-button]").click()
        self.wait_state("viewport", "result")
        page.wait_for_function(
            "n => document.querySelectorAll('[data-testid=history-item]').length === n",
            arg=before + 1,
        )
        self.assertEqual(items.first.get_attribute("data-status"), "done")
        self.assertNotEqual(items.first.get_attribute("data-shot-id"), failed_id)


if __name__ == "__main__":
    unittest.main()
