"""Browser test of version chip click and keyboard use."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class VersionChipsUiTest(unittest.TestCase):
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

    def _two_versions(self):
        h = self.harness
        h.reset()
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(h.url)
        page.locator(tid("shot-description")).fill(DESCRIPTION)
        page.locator(tid("generate-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )
        page.locator(tid("reapply-slider")).evaluate(
            "el => { el.value = '5'; el.dispatchEvent(new Event('input', {bubbles: true})); }"
        )
        page.locator(tid("reapply-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).textContent.trim() === 'Applied f/8'",
            arg=tid("reapply-status"),
        )
        chips = page.locator(tid("version-chip"))
        self.assertEqual(chips.count(), 2)
        return page, chips

    def _wait_label(self, page, text):
        page.wait_for_function(
            "([s, t]) => document.querySelector(s).textContent.trim() === t",
            arg=[tid("label-after"), text],
        )

    def test_click_first_chip_shows_its_version(self):
        page, chips = self._two_versions()
        after = page.locator(tid("after-video"))
        second_src = after.get_attribute("src")
        chips.nth(0).click()
        self._wait_label(page, "After f/2.8")
        self.assertNotEqual(after.get_attribute("src"), second_src)
        self.assertEqual(page.locator(tid("reapply-slider")).input_value(), "2")
        self.assertEqual(page.locator(tid("reapply-value")).text_content().strip(), "f/2.8")
        self.assertEqual(chips.nth(0).get_attribute("aria-pressed"), "true")
        self.assertEqual(chips.nth(1).get_attribute("aria-pressed"), "false")

    def test_enter_and_space_press_chips(self):
        page, chips = self._two_versions()
        chips.nth(0).click()
        self._wait_label(page, "After f/2.8")
        chips.nth(0).focus()
        page.keyboard.press("Tab")
        page.wait_for_function(
            "() => document.activeElement && document.activeElement.dataset.aperture === '8'"
        )
        page.keyboard.press("Enter")
        self._wait_label(page, "After f/8")
        chips = page.locator(tid("version-chip"))
        self.assertEqual(chips.nth(1).get_attribute("aria-pressed"), "true")
        self.assertEqual(chips.nth(0).get_attribute("aria-pressed"), "false")
        chips.nth(0).focus()
        page.keyboard.press("Space")
        self._wait_label(page, "After f/2.8")
        self.assertEqual(chips.nth(0).get_attribute("aria-pressed"), "true")
        self.assertEqual(chips.nth(1).get_attribute("aria-pressed"), "false")


if __name__ == "__main__":
    unittest.main()
