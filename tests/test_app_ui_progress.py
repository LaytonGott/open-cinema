"""Browser test that the shown progress equals the record's progress and never drops."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
BAR = "[data-testid=progress-bar]"


class ProgressTest(unittest.TestCase):
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
        h.reset()
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(h.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def shown(self):
        return int(self.page.locator(BAR).get_attribute("aria-valuenow"))

    def test_shown_progress_matches_record_and_never_drops(self):
        h, fake, page = self.harness, self.harness.fake, self.page
        fake.hold_at("SamplerCustomAdvanced")
        shot_id = None
        seen = []
        try:
            page.locator("[data-testid=shot-description]").fill("A rider crosses a foggy salt flat at dawn.")
            page.locator("[data-testid=generate-button]").click()
            deadline = time.time() + 30
            while time.time() < deadline and shot_id is None:
                code, body = h.get("/api/shots")
                if code == 200 and body["shots"]:
                    shot_id = body["shots"][0]["id"]
                time.sleep(0.05)
            self.assertIsNotNone(shot_id, "no shot was created")
            h.wait_until(shot_id, lambda r: r["status"] == "generating", what="shot generating")
            end = time.time() + 2.5
            while time.time() < end:
                code, record = h.get(f"/api/shots/{shot_id}")
                self.assertEqual(code, 200)
                value = self.shown()
                seen.append(value)
                if record["status"] == "generating":
                    # the page may lag one update behind the record, so bracket it with a second read
                    code, after = h.get(f"/api/shots/{shot_id}")
                    low, high = sorted((round(record["progress"] * 100), round(after["progress"] * 100)))
                    self.assertTrue(low - 1 <= value <= high + 1, f"page {value} vs record {low}..{high}")
                time.sleep(0.1)
        finally:
            fake.release()
        h.wait_for_shot(shot_id, "done")
        page.wait_for_function(
            "s => document.querySelector(s).getAttribute('aria-valuenow') === '100'", arg=BAR
        )
        seen.append(self.shown())
        self.assertEqual(seen, sorted(seen), f"progress dropped: {seen}")
        self.assertEqual(seen[-1], 100)


if __name__ == "__main__":
    unittest.main()
