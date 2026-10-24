"""Browser tests of the design tokens, fonts and that the page makes no foreign requests."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import SHOT, AppHarness

TOKENS = {
    "--bg": "#0b0c0e",
    "--surface": "#14161a",
    "--raised": "#1b1e24",
    "--line": "#262a31",
    "--text": "#e9e6df",
    "--muted": "#9097a2",
    "--accent": "#f5a524",
    "--ok": "#5ad19a",
    "--danger": "#ff6b6b",
}


def tid(name):
    return "[data-testid=%s]" % name


class DesignTest(unittest.TestCase):
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

    def open_page(self, width, height):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        self.requests = []
        self.errors = []
        page.on("request", lambda request: self.requests.append(request.url))
        page.on("console", lambda msg: msg.type == "error" and self.errors.append(msg.text))
        page.goto(self.harness.url)
        page.wait_for_selector(tid("generate-button"))
        return page

    def test_tokens_on_root(self):
        page = self.open_page(1280, 720)
        for name, expected in TOKENS.items():
            value = page.evaluate(
                "n => getComputedStyle(document.documentElement).getPropertyValue(n)", name
            )
            self.assertEqual(value.strip().lower(), expected, name)

    def test_body_background(self):
        page = self.open_page(1280, 720)
        background = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
        self.assertEqual(background, "rgb(11, 12, 14)")

    def test_fonts(self):
        page = self.open_page(1280, 720)
        family = "s => getComputedStyle(document.querySelector(s)).fontFamily"
        for name in ("hud", "aperture-value", "subject-distance"):
            value = page.evaluate(family, tid(name))
            self.assertIn("Consolas", value, name)
            self.assertIn("monospace", value, name)
        body = page.evaluate(family, "body")
        self.assertIn("Segoe UI", body)
        self.assertIn("system-ui", body)

    def test_no_foreign_requests(self):
        self.open_page(1280, 720)
        self.assertTrue(self.requests)
        for url in self.requests:
            if url.startswith("data:") or url.startswith("blob:"):
                continue
            self.assertTrue(url.startswith(self.harness.url), url)
        self.assertEqual(self.errors, [])

    LAYOUT_JS = """() => {
        const box = (s) => {
            const el = document.querySelector(s);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, h: r.height};
        };
        const d = document.documentElement;
        return {
            sw: d.scrollWidth, sh: d.scrollHeight, iw: window.innerWidth, ih: window.innerHeight,
            generate: box('[data-testid=generate-button]'),
            viewport: box('[data-testid=viewport]'),
            history: box('[data-testid=history-list]'),
        };
    }"""

    def check_layout(self, page, tag):
        lay = page.evaluate(self.LAYOUT_JS)
        self.assertLessEqual(lay["sw"], lay["iw"], tag + ": scrollWidth")
        self.assertLessEqual(lay["sh"], lay["ih"], tag + ": scrollHeight")
        generate = lay["generate"]
        self.assertIsNotNone(generate, tag)
        self.assertGreaterEqual(generate["top"], 0, tag + ": generate top")
        self.assertLessEqual(generate["bottom"], lay["ih"], tag + ": generate bottom")
        self.assertLessEqual(generate["right"], lay["iw"], tag + ": generate right")
        self.assertIsNotNone(lay["viewport"], tag)
        history = lay["history"]
        self.assertIsNotNone(history, tag)
        self.assertLessEqual(history["bottom"], lay["ih"] + 1, tag + ": history bottom")
        self.assertGreaterEqual(history["h"], 60, tag + ": history height")
        return lay

    def test_layout_fits_four_sizes(self):
        self.harness.reset()
        status, record = self.harness.post(
            "/api/shots", {**SHOT, "description": "An earlier shot for the history strip.", "seed": 3}
        )
        self.harness.wait_for_shot(record["id"], "done")
        for width, height in ((1280, 720), (1366, 768), (1440, 900), (1536, 864)):
            size = "%dx%d" % (width, height)
            page = self.open_page(width, height)
            page.click(tid("history-new"))
            page.wait_for_timeout(150)
            empty = self.check_layout(page, "empty at " + size)
            page.fill(
                tid("shot-description"),
                "A woman in a red coat crosses a rainy street at night, neon signs in the puddles.",
            )
            self.check_layout(page, "filled at " + size)
            self.harness.fake.stop()
            try:
                page.evaluate("window.dispatchEvent(new Event('focus'))")
                page.wait_for_selector(tid("comfy-banner"), state="visible", timeout=10000)
                down = self.check_layout(page, "down at " + size)
            finally:
                self.harness.fake.start()
            self.assertAlmostEqual(
                empty["history"]["top"], down["history"]["top"], delta=1, msg="history top moved with banner at " + size
            )

    def test_generate_sticky_with_banner(self):
        page = self.open_page(1280, 720)
        self.harness.fake.stop()
        try:
            page.evaluate("window.dispatchEvent(new Event('focus'))")
            page.wait_for_selector(tid("comfy-banner"), state="visible", timeout=10000)
            for where in ("0", "scrollHeight"):
                page.evaluate("w => { const d = document.querySelector('#director'); d.scrollTop = w === '0' ? 0 : d.scrollHeight; }", where)
                page.wait_for_timeout(100)
                lay = page.evaluate(self.LAYOUT_JS)
                generate = lay["generate"]
                self.assertIsNotNone(generate, where)
                self.assertGreaterEqual(generate["top"], 0, where + ": generate top")
                self.assertLessEqual(generate["bottom"], lay["ih"], where + ": generate bottom")
                self.assertGreaterEqual(generate["left"], 0, where + ": generate left")
                self.assertLessEqual(generate["right"], lay["iw"], where + ": generate right")
        finally:
            self.harness.fake.start()

    def test_generate_style(self):
        page = self.open_page(1280, 720)
        page.click(tid("history-new"))
        page.wait_for_timeout(150)
        page.fill(tid("shot-description"), "")
        style = "s => { const c = getComputedStyle(document.querySelector(s)); return [c.backgroundColor, c.cursor]; }"
        button = tid("generate-button")
        self.assertTrue(page.is_disabled(button))
        disabled_background, disabled_cursor = page.evaluate(style, button)
        self.assertEqual(disabled_cursor, "not-allowed")
        page.fill(tid("shot-description"), "A woman in a red coat crosses a rainy street at night.")
        self.assertTrue(page.is_enabled(button))
        page.wait_for_function(
            "s => getComputedStyle(document.querySelector(s)).backgroundColor === 'rgb(245, 165, 36)'",
            arg=button,
        )
        background, cursor = page.evaluate(style, button)
        self.assertEqual(background, "rgb(245, 165, 36)")
        self.assertEqual(cursor, "pointer")
        self.assertNotEqual(disabled_background, background)


if __name__ == "__main__":
    unittest.main()
