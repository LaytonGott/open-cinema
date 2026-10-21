"""Browser test of keyboard use of the shot form."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"
GENERATE = "[data-testid=generate-button]"


class FormKeyboardTest(unittest.TestCase):
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
        self.harness.fake.release()
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(self.harness.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def shot_ids(self):
        code, body = self.harness.get("/api/shots")
        self.assertEqual(code, 200)
        return [s["id"] for s in body["shots"]]

    def test_space_selects_focused_radio(self):
        radio = self.page.locator("[data-testid=lens-group] [role=radio][data-value='35']")
        radio.wait_for()
        # earlier tests leave shots behind; the HUD shows the restored shot until a new one is started
        self.page.locator("[data-testid=history-new]").click()
        self.page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'empty'"
        )
        radio.focus()
        radio.press("Space")
        self.page.wait_for_function(
            "() => document.querySelector('[data-testid=lens-group] [data-value=\"35\"]')"
            ".getAttribute('aria-checked') === 'true'"
        )
        self.page.wait_for_function(
            "() => document.querySelector('[data-testid=hud]').textContent.includes('35 mm')"
        )

    def test_only_checked_radio_is_tab_stop(self):
        for name in ("camera-group", "lens-group", "framing-group"):
            with self.subTest(group=name):
                radios = self.page.locator(f"[data-testid={name}] [role=radio]")
                radios.first.wait_for()
                stops = [b for b in radios.all() if b.get_attribute("tabindex") == "0"]
                self.assertEqual(len(stops), 1)
                self.assertEqual(stops[0].get_attribute("aria-checked"), "true")

    def test_generate_button_disabled_until_text_and_enter_key_submits(self):
        button = self.page.locator(GENERATE)
        self.assertTrue(button.is_disabled())
        before = self.shot_ids()
        self.page.locator("[data-testid=shot-description]").fill("A dog runs on a beach")
        self.page.wait_for_function("s => !document.querySelector(s).disabled", arg=GENERATE)
        button.focus()
        button.press("Enter")
        new = []
        try:
            deadline = time.time() + 15
            while time.time() < deadline and not new:
                new = [i for i in self.shot_ids() if i not in before]
                time.sleep(0.1)
            self.assertEqual(len(new), 1)
        finally:
            self.harness.fake.release()
        self.harness.wait_for_shot(new[0])


if __name__ == "__main__":
    unittest.main()
