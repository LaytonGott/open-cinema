"""Browser test of the history strip: item count, newest first, title, lens, aperture and framing."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"
DESCRIPTION = "A rider crosses a foggy salt flat at dawn, slowly."


class HistoryTest(unittest.TestCase):
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

    def generate(self, description):
        self.page.locator("[data-testid=shot-description]").fill(description)
        self.page.locator("[data-testid=generate-button]").click()
        self.wait_state("viewport", "result")

    def check_items(self):
        code, body = self.harness.get("/api/shots")
        self.assertEqual(code, 200)
        self.page.wait_for_function(
            "n => document.querySelectorAll('[data-testid=history-item]').length === n",
            arg=len(body["shots"]),
        )
        items = self.page.locator("[data-testid=history-item]")
        self.assertEqual(items.count(), len(body["shots"]))
        return body["shots"], items

    def test_history_items(self):
        self.assertGreater(len(DESCRIPTION), 41)
        self.generate(DESCRIPTION)
        shots, items = self.check_items()
        first, shot = items.nth(0), shots[0]
        self.assertEqual(first.get_attribute("data-status"), "done")
        self.assertTrue(first.get_attribute("data-shot-id"))
        self.assertEqual(first.get_attribute("data-shot-id"), shot["id"])
        text = first.inner_text()
        self.assertIn(DESCRIPTION[:40], text)
        self.assertNotIn(DESCRIPTION[:41], text)
        self.assertNotIn(DESCRIPTION[40:], text)
        params = shot["params"]
        code, options = self.harness.get("/api/options")
        label = next(f["label"] for f in options["framings"] if f["id"] == params["framing"])
        self.assertIn(f"{params['lens_mm']}mm", text)
        self.assertIn(f"f/{params['aperture']}", text)
        self.assertIn(label, text)

        previous = shot["id"]
        self.generate("A second shot of a lighthouse keeper at night.")
        shots, items = self.check_items()
        self.assertNotEqual(shots[0]["id"], previous)
        self.assertEqual(items.nth(0).get_attribute("data-shot-id"), shots[0]["id"])
        self.assertEqual(items.nth(1).get_attribute("data-shot-id"), previous)

    def test_history_status_updates_live(self):
        fake, page = self.harness.fake, self.page
        item = page.locator("[data-testid=history-item]").first
        fake.hold_at("SamplerCustomAdvanced")
        try:
            page.locator("[data-testid=shot-description]").fill(DESCRIPTION)
            page.locator("[data-testid=generate-button]").click()
            page.wait_for_function(
                "() => { const e = document.querySelector('[data-testid=history-item]');"
                " return e && e.dataset.status !== 'done' && e.dataset.status !== 'failed'"
                " && e.dataset.status !== 'cancelled'; }"
            )
            self.assertNotIn(item.get_attribute("data-status"), TERMINAL)
        finally:
            fake.release()
        page.wait_for_function(
            "() => { const e = document.querySelector('[data-testid=history-item]');"
            " return e && e.dataset.status === 'done'; }"
        )


if __name__ == "__main__":
    unittest.main()
