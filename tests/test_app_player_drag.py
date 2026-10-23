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

    def test_touch_drag(self):
        page = self.finished_page()
        slider = page.locator(tid("compare-slider"))
        handle = page.locator(tid("compare-handle"))
        handle.wait_for(state="visible")
        box = slider.bounding_box()
        hbox = handle.bounding_box()
        start_x = hbox["x"] + hbox["width"] / 2
        y = box["y"] + box["height"] / 2
        target_x = box["x"] + box["width"] * 0.25
        page.evaluate(
            """([startX, targetX, y]) => {
                const handle = document.querySelector('[data-testid=compare-handle]');
                // A synthetic pointer id is not an active pointer, so capture would throw.
                handle.parentElement.setPointerCapture = () => {};
                const fire = (el, type, x) => el.dispatchEvent(new PointerEvent(type, {
                    pointerId: 7, pointerType: 'touch', isPrimary: true,
                    clientX: x, clientY: y, bubbles: true, cancelable: true,
                }));
                fire(handle, 'pointerdown', startX);
                fire(handle, 'pointermove', (startX + targetX) / 2);
                fire(handle, 'pointermove', targetX);
                fire(handle, 'pointerup', targetX);
            }""",
            [start_x, target_x, y],
        )
        page.wait_for_function(
            "() => Math.abs(Number(document.querySelector('[data-testid=compare-slider]')"
            ".getAttribute('aria-valuenow')) - 25) <= 3"
        )
        value = float(slider.get_attribute("aria-valuenow"))
        self.assertAlmostEqual(value, 25, delta=3)
        self.assertEqual(page.evaluate("window.scrollY"), 0)

    def test_track_click(self):
        page = self.finished_page()
        slider = page.locator(tid("compare-slider"))
        slider.wait_for(state="visible")
        box = slider.bounding_box()
        page.mouse.click(box["x"] + box["width"] * 0.75, box["y"] + box["height"] / 2)
        page.wait_for_function(
            "() => Math.abs(Number(document.querySelector('[data-testid=compare-slider]')"
            ".getAttribute('aria-valuenow')) - 75) <= 3"
        )
        value = float(slider.get_attribute("aria-valuenow"))
        self.assertAlmostEqual(value, 75, delta=3)

    def test_no_change_after_release(self):
        page = self.finished_page()
        slider = page.locator(tid("compare-slider"))
        handle = page.locator(tid("compare-handle"))
        handle.wait_for(state="visible")
        box = slider.bounding_box()
        hbox = handle.bounding_box()
        start_x = hbox["x"] + hbox["width"] / 2
        y = box["y"] + box["height"] / 2
        target_x = box["x"] + box["width"] * 0.4
        page.mouse.move(start_x, y)
        page.mouse.down()
        page.mouse.move((start_x + target_x) / 2, y, steps=5)
        page.mouse.move(target_x, y, steps=5)
        page.mouse.up()
        page.wait_for_function(
            "() => Math.abs(Number(document.querySelector('[data-testid=compare-slider]')"
            ".getAttribute('aria-valuenow')) - 40) <= 3"
        )
        released = slider.get_attribute("aria-valuenow")
        page.mouse.move(box["x"] + box["width"] * 0.9, y, steps=5)
        page.mouse.move(box["x"] + box["width"] * 0.1, y, steps=5)
        self.assertEqual(slider.get_attribute("aria-valuenow"), released)


if __name__ == "__main__":
    unittest.main()
