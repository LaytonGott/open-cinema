"""Browser test of how the optics controls look in a result at four window sizes."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."
SIZES = ((1280, 720), (1366, 768), (1440, 900), (1536, 864))


def tid(name):
    return "[data-testid=%s]" % name


class DesignOpticsTest(unittest.TestCase):
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
        page.wait_for_function(
            "s => document.querySelector(s).textContent.trim() === 'After f/8'", arg=tid("label-after")
        )
        page.wait_for_function(
            "() => document.querySelector('[data-testid=reapply-slider]').value === '5'"
        )
        return page, chips

    def test_controls_fit_at_four_sizes(self):
        page, _ = self._two_versions()
        for width, height in SIZES:
            with self.subTest(size="%dx%d" % (width, height)):
                page.set_viewport_size({"width": width, "height": height})
                fit = page.evaluate(
                    """() => ({
                        sh: document.documentElement.scrollHeight, ih: window.innerHeight,
                        sw: document.documentElement.scrollWidth, iw: window.innerWidth,
                    })"""
                )
                self.assertLessEqual(fit["sh"], fit["ih"])
                self.assertLessEqual(fit["sw"], fit["iw"])
                box = page.locator(tid("optics-controls")).bounding_box()
                self.assertGreaterEqual(box["x"], 0)
                self.assertGreaterEqual(box["y"], 0)
                self.assertLessEqual(box["x"] + box["width"], width)
                self.assertLessEqual(box["y"] + box["height"], height)

    def test_apply_button_and_chips_styling(self):
        page, chips = self._two_versions()
        button = page.locator(tid("reapply-button"))
        slider = page.locator(tid("reapply-slider"))
        self.assertTrue(button.is_disabled())
        style = button.evaluate(
            """el => {
                const probe = document.createElement('span');
                probe.style.color = 'var(--accent)';
                document.body.appendChild(probe);
                const accent = getComputedStyle(probe).color;
                probe.remove();
                const cs = getComputedStyle(el);
                return {opacity: parseFloat(cs.opacity), background: cs.backgroundColor, accent: accent};
            }"""
        )
        self.assertLess(style["opacity"], 1)
        self.assertNotEqual(style["background"], style["accent"])
        slider.evaluate(
            "el => { el.value = '3'; el.dispatchEvent(new Event('input', {bubbles: true})); }"
        )
        page.wait_for_function(
            "s => !document.querySelector(s).disabled", arg=tid("reapply-button")
        )
        self.assertTrue(button.is_enabled())

        self.assertEqual(chips.nth(1).get_attribute("aria-pressed"), "true")
        self.assertEqual(chips.nth(0).get_attribute("aria-pressed"), "false")
        shown = chips.nth(1).evaluate("el => getComputedStyle(el).borderColor")
        other = chips.nth(0).evaluate("el => getComputedStyle(el).borderColor")
        self.assertNotEqual(shown, other)


if __name__ == "__main__":
    unittest.main()
