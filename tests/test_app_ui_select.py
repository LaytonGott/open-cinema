"""Browser test of selecting a finished shot from the history strip after a reload."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn, slowly."


class SelectTest(unittest.TestCase):
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
        for shot in body["shots"]:
            h.request("DELETE", "/api/shots/" + shot["id"])
        h.reset()
        self.addCleanup(h.fake.clear_failures)
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(h.url)
        self.wait_status()

    def wait_status(self):
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def wait_state(self, testid, state):
        self.page.wait_for_function(
            "([s, v]) => document.querySelector(s) && document.querySelector(s).dataset.state === v",
            arg=[f"[data-testid={testid}]", state],
        )

    def test_select_finished_shot(self):
        page = self.page
        page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
        page.locator("[data-testid=generate-button]").click()
        self.wait_state("viewport", "result")
        code, body = self.harness.get("/api/shots")
        self.assertEqual(code, 200)
        lens = f"{body['shots'][0]['params']['lens_mm']}mm"

        page.reload()
        self.wait_status()
        item = page.locator("[data-testid=history-item]").first
        item.wait_for()
        item.click()
        self.wait_state("viewport", "result")
        page.wait_for_function(
            "([s, v]) => document.querySelector(s) && document.querySelector(s).textContent.replace(/\\s/g, '').includes(v)",
            arg=["[data-testid=hud]", lens],
        )
        hud = page.locator("[data-testid=hud]")
        self.assertIn(lens, hud.inner_text().replace(" ", ""))

    def test_switch_finished_and_running(self):
        page, fake = self.page, self.harness.fake
        items = page.locator("[data-testid=history-item]")
        self.addCleanup(fake.release)
        page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
        page.locator("[data-testid=generate-button]").click()
        self.wait_state("viewport", "result")
        items.first.wait_for()
        x_id = items.first.get_attribute("data-shot-id")

        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        page.locator("[data-testid=generate-button]").click()
        self.wait_state("viewport", "working")
        page.wait_for_function(
            "id => document.querySelector('[data-testid=history-item]').dataset.shotId !== id", arg=x_id
        )
        y_id = items.first.get_attribute("data-shot-id")
        self.assertNotEqual(x_id, y_id)

        page.locator(f"[data-testid=history-item][data-shot-id='{x_id}']").click()
        self.wait_state("viewport", "result")
        page.locator(f"[data-testid=history-item][data-shot-id='{y_id}']").click()
        self.wait_state("viewport", "working")

        fake.release()
        self.wait_state("viewport", "result")


if __name__ == "__main__":
    unittest.main()
