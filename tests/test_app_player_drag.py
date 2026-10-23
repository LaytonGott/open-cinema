"""Browser test of dragging the compare handle with the mouse."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class PlayerDragTest(unittest.TestCase):
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

    def finished_page(self):
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
        return page

    def test_mouse_drag(self):
        page = self.finished_page()
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
        value = float(slider.get_attribute("aria-valuenow"))
        self.assertAlmostEqual(value, 25, delta=3)


if __name__ == "__main__":
    unittest.main()
