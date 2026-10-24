"""Browser test of the refined compare divider, handle, labels and focus ring."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class DesignDividerTest(unittest.TestCase):
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

    def label_xs(self, page):
        return page.evaluate(
            """() => {
                const p = document.querySelector('[data-testid=player]').getBoundingClientRect();
                const r = s => document.querySelector('[data-testid=' + s + ']').getBoundingClientRect();
                const b = r('label-before'), a = r('label-after');
                return {pw: p.width, ph: p.height, bx: b.left - p.left, by: b.top - p.top,
                        ax: p.right - a.right, ay: a.top - p.top, bleft: b.left, aleft: a.left};
            }"""
        )

    def test_round_handle_with_two_svgs_and_thin_line(self):
        page = self.finished_page()
        handle = page.locator(tid("compare-handle"))
        handle.wait_for(state="visible")
        self.assertGreaterEqual(handle.locator("svg").count(), 2)
        knob = page.evaluate(
            """() => {
                const k = document.querySelector('[data-testid=compare-handle] .compare-knob');
                const r = k.getBoundingClientRect();
                return {w: r.width, h: r.height, radius: getComputedStyle(k).borderTopLeftRadius};
            }"""
        )
        self.assertAlmostEqual(knob["w"], knob["h"], delta=0.5)
        radius = knob["radius"]
        self.assertTrue(
            (radius.endswith("%") and float(radius[:-1]) >= 50)
            or (radius.endswith("px") and float(radius[:-2]) >= knob["w"] / 2),
            radius,
        )
        line = page.evaluate(
            "() => parseFloat(getComputedStyle(document.querySelector("
            "'[data-testid=compare-handle]'), '::before').width)"
        )
        self.assertLessEqual(line, 3)

    def test_keyboard_and_drag_move_slider_labels_stay(self):
        page = self.finished_page()
        slider = page.locator(tid("compare-slider"))
        handle = page.locator(tid("compare-handle"))
        handle.wait_for(state="visible")
        before = self.label_xs(page)
        self.assertLess(before["bx"], before["pw"] / 2)
        self.assertLess(before["ax"], before["pw"] / 2)
        self.assertLess(before["by"], before["ph"] / 2)
        self.assertLess(before["ay"], before["ph"] / 2)
        self.assertLess(before["bleft"], before["aleft"])
        start = float(slider.get_attribute("aria-valuenow"))
        slider.focus()
        page.keyboard.press("ArrowRight")
        page.wait_for_function(
            "v => Number(document.querySelector('[data-testid=compare-slider]')"
            ".getAttribute('aria-valuenow')) !== v",
            arg=start,
        )
        after_key = float(slider.get_attribute("aria-valuenow"))
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
            "v => Number(document.querySelector('[data-testid=compare-slider]')"
            ".getAttribute('aria-valuenow')) !== v",
            arg=after_key,
        )
        after = self.label_xs(page)
        self.assertAlmostEqual(after["bx"], before["bx"], delta=1)
        self.assertAlmostEqual(after["ax"], before["ax"], delta=1)

    def test_focus_ring_uses_accent(self):
        page = self.finished_page()
        page.locator(tid("compare-handle")).wait_for(state="visible")
        for _ in range(60):
            page.keyboard.press("Tab")
            if page.evaluate(
                "() => document.activeElement === document.querySelector('[data-testid=compare-slider]')"
            ):
                break
        else:
            self.fail("Tab never reached the compare slider")
        ring = page.evaluate(
            """() => {
                const s = getComputedStyle(document.querySelector('[data-testid=compare-slider]'));
                const k = getComputedStyle(document.querySelector('[data-testid=compare-slider] .compare-knob'));
                return [s.outline, s.boxShadow, k.outline, k.boxShadow].join(' | ');
            }"""
        )
        self.assertIn("rgb(245, 165, 36)", ring)


if __name__ == "__main__":
    unittest.main()
