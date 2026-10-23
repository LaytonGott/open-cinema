"""Browser test that using the player controls logs no console errors, failed requests or foreign hosts."""
import unittest
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class Recorder:
    """Collects console errors, page errors, failed requests and every request URL of a page."""

    def __init__(self, page):
        self.errors = []
        self.pageerrors = []
        self.failed = []
        self.urls = []
        page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: self.pageerrors.append(str(e)))
        page.on("requestfailed", lambda r: self.failed.append(r.url))
        page.on("request", lambda r: self.urls.append(r.url))

    def assert_clean(self, test, app_url):
        """Assert no errors were recorded and every request went to the app host."""
        test.assertEqual(self.errors, [])
        test.assertEqual(self.pageerrors, [])
        test.assertEqual(self.failed, [])
        test.assertTrue(self.urls)
        host = urlparse(app_url).netloc
        foreign = [u for u in self.urls if urlparse(u).netloc != host and not u.startswith(("data:", "blob:"))]
        test.assertEqual(foreign, [])


class PlayerCleanTest(unittest.TestCase):
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

    def test_play_scrub_drag_clean(self):
        h = self.harness
        h.reset()
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        rec = Recorder(page)
        page.goto(h.url)
        page.locator(tid("shot-description")).fill(DESCRIPTION)
        page.locator(tid("generate-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )
        page.wait_for_function(
            "() => { const t = document.querySelector('[data-testid=play-toggle]');"
            " return !!t && !t.disabled; }"
        )

        page.locator(tid("play-toggle")).click()
        page.evaluate(
            "() => { const s = document.querySelector('[data-testid=scrubber]');"
            " s.value = 500; s.dispatchEvent(new Event('input', {bubbles: true})); }"
        )

        slider = page.locator(tid("compare-slider"))
        handle = page.locator(tid("compare-handle"))
        handle.wait_for(state="visible")
        box = slider.bounding_box()
        hbox = handle.bounding_box()
        start_x = hbox["x"] + hbox["width"] / 2
        y = box["y"] + box["height"] / 2
        target_x = box["x"] + box["width"] * 0.25
        page.mouse.move(start_x, y)
        page.mouse.down()
        page.mouse.move((start_x + target_x) / 2, y, steps=5)
        page.mouse.move(target_x, y, steps=5)
        page.mouse.up()
        page.wait_for_function(
            "() => Math.abs(Number(document.querySelector('[data-testid=compare-slider]')"
            ".getAttribute('aria-valuenow')) - 25) <= 3"
        )

        rec.assert_clean(self, h.url)


if __name__ == "__main__":
    unittest.main()
