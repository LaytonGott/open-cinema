"""Browser test of history item details (lens, aperture, framing, status, BUTTON) and the aria-current mark."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import TERMINAL, AppHarness

STATUS = "[data-testid=comfy-status]"


class HistoryDetailsTest(unittest.TestCase):
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
        h.fake.reset_cache()
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

    def pick(self, group, value):
        self.page.locator(f"[data-testid={group}] [role=radio][data-value='{value}']").click()

    def shoot(self, lens, framing, description):
        self.pick("lens-group", lens)
        self.pick("framing-group", framing)
        self.page.locator("[data-testid=shot-description]").fill(description)
        self.page.locator("[data-testid=generate-button]").click()
        self.wait_state("viewport", "result")

    def current_ids(self):
        return self.page.evaluate(
            "() => [...document.querySelectorAll('[data-testid=history-item]')]"
            ".filter(e => e.getAttribute('aria-current') === 'true').map(e => e.dataset.shotId)"
        )

    def test_details_and_selection_mark(self):
        self.shoot("50", "full-body", "First shot of a rider on a salt flat.")
        self.shoot("35", "waist-up", "Second shot of a lighthouse keeper.")
        code, body = self.harness.get("/api/shots")
        self.assertEqual(code, 200)
        shots = body["shots"]
        self.assertEqual(len(shots), 2)
        self.page.wait_for_function(
            "() => { const l = [...document.querySelectorAll('[data-testid=history-item]')];"
            " return l.length === 2 && l.every(e => e.dataset.status === 'done'"
            " && e.innerText.includes('done')); }"
        )
        code, options = self.harness.get("/api/options")
        labels = {f["id"]: f["label"] for f in options["framings"]}
        items = self.page.locator("[data-testid=history-item]")
        expected = [("35mm", "waist-up"), ("50mm", "full-body")]
        for i, (lens, framing) in enumerate(expected):
            item, shot = items.nth(i), shots[i]
            self.assertEqual(item.evaluate("e => e.tagName"), "BUTTON")
            self.assertEqual(item.get_attribute("data-shot-id"), shot["id"])
            self.assertEqual(item.get_attribute("data-status"), "done")
            self.assertEqual(shot["params"]["framing"], framing)
            text = item.inner_text()
            self.assertIn(lens, text)
            self.assertIn(f"f/{shot['params']['aperture']}", text)
            self.assertIn(labels[framing], text)
            self.assertIn("done", text)
        self.assertEqual(self.current_ids(), [shots[0]["id"]])
        items.nth(1).click()
        self.page.wait_for_function(
            "id => { const e = document.querySelector('[data-testid=history-item][aria-current=true]');"
            " return e && e.dataset.shotId === id; }",
            arg=shots[1]["id"],
        )
        self.assertEqual(self.current_ids(), [shots[1]["id"]])


if __name__ == "__main__":
    unittest.main()
