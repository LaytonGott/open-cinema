"""Browser test of the filmstrip design: the history strip scrolls inside itself, equal cards, accent on the shown card."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import SHOT, AppHarness

STATUS = "[data-testid=comfy-status]"
ITEMS = "[data-testid=history-item]"
COUNT = 12
ACCENT = "rgb(245, 165, 36)"


class FilmstripTest(unittest.TestCase):
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
        h.reset()
        for seed in range(1, COUNT + 1):
            status, body = h.post("/api/shots", {**SHOT, "seed": seed})
            self.assertIn(status, (200, 201, 202))
            h.wait_for_shot(body["id"])
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 720})
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(h.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )
        self.page.wait_for_function("n => document.querySelectorAll('%s').length === n" % ITEMS, arg=COUNT)
        self.page.wait_for_function("() => !!document.querySelector('%s[aria-current=true]')" % ITEMS)

    def test_strip_scrolls_inside_itself(self):
        m = self.page.evaluate(
            "() => { const l = document.querySelector('[data-testid=history-list]');"
            " const d = document.documentElement;"
            " return {lw: l.scrollWidth, lc: l.clientWidth, dw: d.scrollWidth, iw: window.innerWidth}; }"
        )
        self.assertGreater(m["lw"], m["lc"])
        self.assertLessEqual(m["dw"], m["iw"])

    def test_cards_equal_size(self):
        sizes = self.page.evaluate(
            "() => [...document.querySelectorAll('%s')].map(e => { const r = e.getBoundingClientRect();"
            " return [Math.round(r.width), Math.round(r.height)]; })" % ITEMS
        )
        self.assertEqual(len(sizes), COUNT)
        self.assertEqual(len({tuple(s) for s in sizes}), 1, sizes)

    def test_selected_card_accent_and_switching(self):
        page = self.page
        current = page.locator(ITEMS + "[aria-current=true]")
        self.assertEqual(current.count(), 1)
        # The border colour eases in over 150 ms after the card is selected.
        page.wait_for_function(
            "([s, c]) => getComputedStyle(document.querySelector(s)).borderTopColor === c",
            arg=[ITEMS + "[aria-current=true]", ACCENT],
        )
        self.assertEqual(current.evaluate("e => getComputedStyle(e).borderTopColor"), ACCENT)
        shown = current.get_attribute("data-shot-id")
        other = page.locator(ITEMS + ":not([aria-current=true])").nth(2)
        other_id = other.get_attribute("data-shot-id")
        self.assertNotEqual(other_id, shown)
        other.scroll_into_view_if_needed()
        other.click()
        page.wait_for_function(
            "id => { const e = document.querySelector('%s[aria-current=true]'); return e && e.dataset.shotId === id; }" % ITEMS,
            arg=other_id,
        )
        self.assertEqual(page.locator(ITEMS + "[aria-current=true]").count(), 1)
        self.assertEqual(page.locator(ITEMS + "[data-shot-id='%s']" % shown).get_attribute("aria-current"), None)

    def test_new_button_first_and_status_dot_hidden(self):
        page = self.page
        new = page.locator("[data-testid=history-new]").bounding_box()
        first = page.locator(ITEMS).first.bounding_box()
        self.assertLess(new["x"] + new["width"], first["x"] + 1)
        first_item = page.locator(ITEMS).first
        self.assertEqual(first_item.locator(".status-dot").get_attribute("aria-hidden"), "true")
        self.assertTrue(first_item.locator(".history-status").is_visible())
        self.assertTrue(first_item.locator(".history-status").inner_text().strip())


if __name__ == "__main__":
    unittest.main()
