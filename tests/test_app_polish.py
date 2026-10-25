"""Browser tests of visual polish details in the director app."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"

JS_ACCENT = """() => {
  const probe = document.createElement('span');
  probe.style.color = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
  document.body.appendChild(probe);
  const accent = getComputedStyle(probe).color;
  probe.remove();
  return accent;
}"""

JS_BORDER = "s => getComputedStyle(document.querySelector(s)).borderTopColor"


class PolishTests(unittest.TestCase):
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
        self.harness.reset()
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 720})
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(self.harness.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def test_selected_camera_and_framing_have_accent_border(self):
        page = self.page
        accent = page.evaluate(JS_ACCENT)
        for group, value in (("camera-group", "dolly-in"), ("framing-group", "close-up")):
            with self.subTest(group=group):
                base = f"[data-testid={group}] button[role=radio]"
                selected = f"{base}[data-value='{value}']"
                page.locator(selected).click()
                page.wait_for_function(
                    "s => document.querySelector(s).getAttribute('aria-checked') === 'true'", arg=selected
                )
                unselected = f"{base}[aria-checked=false]"
                page.wait_for_function(
                    "([s, c]) => getComputedStyle(document.querySelector(s)).borderTopColor === c",
                    arg=[selected, accent],
                )
                self.assertEqual(page.evaluate(JS_BORDER, selected), accent)
                self.assertNotEqual(page.evaluate(JS_BORDER, unselected), accent)
                self.assertNotEqual(page.evaluate(JS_BORDER, unselected), page.evaluate(JS_BORDER, selected))


if __name__ == "__main__":
    unittest.main()
