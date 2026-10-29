"""Browser test of the shot form option groups (camera, lens, framing)."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"
GROUPS = {
    "camera-group": ("Camera move", ["static", "dolly-in", "dolly-out", "pan-left", "pan-right", "tilt-up", "orbit", "handheld"]),
    "lens-group": ("Lens", ["24", "35", "50", "85"]),
    "framing-group": ("Framing", ["close-up", "waist-up", "full-body", "wide"]),
}
DEFAULTS = {"camera-group": "static", "lens-group": "50", "framing-group": "full-body"}


class FormGroupsTest(unittest.TestCase):
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

    def group(self, name):
        return self.page.locator(f"[data-testid={name}]")

    def buttons(self, name):
        loc = self.group(name).locator("[role=radio]")
        loc.first.wait_for()
        return loc

    def checked(self, name):
        return [
            b.get_attribute("data-value")
            for b in self.buttons(name).all()
            if b.get_attribute("aria-checked") == "true"
        ]

    def test_group_values_and_names(self):
        for name, (label, values) in GROUPS.items():
            with self.subTest(group=name):
                self.assertEqual(self.group(name).get_attribute("role"), "radiogroup")
                self.assertEqual(self.page.get_by_role("radiogroup", name=label, exact=True).count(), 1)
                got = [b.get_attribute("data-value") for b in self.buttons(name).all()]
                self.assertEqual(got, values)

    def test_lens_texts(self):
        texts = [b.inner_text().strip() for b in self.buttons("lens-group").all()]
        self.assertEqual(texts, ["24 mm", "35 mm", "50 mm", "85 mm"])

    def test_defaults(self):
        for name, default in DEFAULTS.items():
            with self.subTest(group=name):
                self.assertEqual(self.checked(name), [default])

    def test_click_lens(self):
        self.page.get_by_role("radio", name="24 mm").click()
        self.page.wait_for_function(
            "() => document.querySelector('[data-testid=lens-group] [data-value=\"24\"]')"
            ".getAttribute('aria-checked') === 'true'"
        )
        self.assertEqual(self.checked("lens-group"), ["24"])

    def shot_ids(self):
        code, body = self.harness.get("/api/shots")
        self.assertEqual(code, 200)
        return [s["id"] for s in body["shots"]]

    def test_ctrl_enter_empty_creates_no_shot(self):
        before = self.shot_ids()
        ta = self.page.locator("[data-testid=shot-description]")
        ta.focus()
        ta.press("Control+Enter")
        # a stray submit would show up as a request; wait until the page has settled, then compare
        self.page.wait_for_function("() => document.querySelector('[data-testid=generate-button]').disabled")
        self.assertEqual(self.shot_ids(), before)
        self.assertFalse(self.page.locator("[data-testid=status-panel]").is_visible())

    def test_ctrl_enter_with_text_creates_shot(self):
        before = self.shot_ids()
        ta = self.page.locator("[data-testid=shot-description]")
        ta.fill("A dog runs on a beach")
        ta.press("Control+Enter")
        try:
            deadline = time.time() + 15
            new = []
            while time.time() < deadline and not new:
                new = [i for i in self.shot_ids() if i not in before]
                time.sleep(0.1)
            self.assertEqual(len(new), 1)
        finally:
            self.harness.fake.release()
        self.harness.wait_for_shot(new[0])


if __name__ == "__main__":
    unittest.main()
