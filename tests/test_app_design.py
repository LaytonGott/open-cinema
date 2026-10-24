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

    def test_hud_follows_form_and_background(self):
        self.harness.reset()
        page = self.open_page(1280, 720)
        page.click(tid("history-new"))
        before = page.inner_text(tid("hud"))
        page.click(tid("lens-group") + " [data-value='85']")
        page.fill(tid("aperture-slider"), "5")
        page.wait_for_function(
            "([s, old]) => { const t = document.querySelector(s).textContent;"
            " return t !== old && t.includes('f/8') && t.includes('85'); }",
            arg=[tid("hud"), before],
        )
        info = page.evaluate(
            """() => {
                const hud = document.querySelector('[data-testid=hud]');
                const view = document.querySelector('[data-testid=viewport]').getBoundingClientRect();
                const box = hud.getBoundingClientRect();
                const style = getComputedStyle(hud);
                return {background: style.backgroundColor, family: style.fontFamily,
                        hudBottom: box.bottom, hudWidth: box.width,
                        viewBottom: view.bottom, viewWidth: view.width};
            }"""
        )
        channels = [float(v) for v in info["background"].split("(")[1].rstrip(")").split(",")]
        alpha = channels[3] if len(channels) > 3 else 1.0
        self.assertGreaterEqual(alpha, 0.35, info["background"])
        for value in channels[:3]:
            self.assertLess(value, 80, info["background"])
        self.assertAlmostEqual(info["hudBottom"], info["viewBottom"], delta=1)
        self.assertAlmostEqual(info["hudWidth"], info["viewWidth"], delta=2)
        self.assertIn("monospace", info["family"])

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

    def test_banner_layout(self):
        self.harness.reset()
        for width, height in ((1280, 720), (1366, 768), (1440, 900), (1536, 864)):
            size = "%dx%d" % (width, height)
            page = self.open_page(width, height)
            self.harness.fake.stop()
            try:
                page.evaluate("window.dispatchEvent(new Event('focus'))")
                page.wait_for_selector(tid("comfy-banner"), state="visible", timeout=10000)
                header_bottom = page.evaluate("document.querySelector('header').getBoundingClientRect().bottom")
                banner_top = page.evaluate(
                    "s => document.querySelector(s).getBoundingClientRect().top", tid("comfy-banner")
                )
                self.assertGreaterEqual(banner_top, header_bottom - 0.5, "banner below header at " + size)
                self.check_layout(page, "down at " + size)
            finally:
                self.harness.fake.start()
            page.click(tid("comfy-retry"))
            page.wait_for_selector(tid("comfy-banner"), state="hidden", timeout=10000)
            self.check_layout(page, "retried at " + size)

    BRACKETS_JS = """() => {
        const box = (el) => {
            const r = el.getBoundingClientRect();
            return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, w: r.width, h: r.height};
        };
        const hint = document.querySelector('[data-testid=viewport-hint]');
        return {
            viewport: box(document.querySelector('[data-testid=viewport]')),
            director: box(document.querySelector('#director')),
            history: box(document.querySelector('#history')),
            marks: Array.from(document.querySelectorAll('[data-testid=crop-mark]')).map(box),
            hint: hint && {visible: hint.offsetParent !== null || getComputedStyle(hint).position === 'fixed',
                           text: hint.textContent.trim()},
        };
    }"""

    @staticmethod
    def boxes_intersect(a, b):
        return a["left"] < b["right"] and b["left"] < a["right"] and a["top"] < b["bottom"] and b["top"] < a["bottom"]

    def check_brackets(self, page, tag, hint):
        lay = page.evaluate(self.BRACKETS_JS)
        view = lay["viewport"]
        self.assertGreaterEqual(view["w"], 560, tag + ": width")
        self.assertTrue(1.7 <= view["w"] / view["h"] <= 1.95, "%s: ratio %s" % (tag, view["w"] / view["h"]))
        self.assertFalse(self.boxes_intersect(view, lay["director"]), tag + ": director")
        self.assertFalse(self.boxes_intersect(view, lay["history"]), tag + ": history")
        self.assertEqual(len(lay["marks"]), 4, tag)
        for mark in lay["marks"]:
            self.assertGreater(mark["w"], 0, tag + ": mark width")
            self.assertGreaterEqual(mark["left"], view["left"] - 1, tag)
            self.assertGreaterEqual(mark["top"], view["top"] - 1, tag)
            self.assertLessEqual(mark["right"], view["right"] + 1, tag)
            self.assertLessEqual(mark["bottom"], view["bottom"] + 1, tag)
        for mark in page.query_selector_all(tid("crop-mark")):
            self.assertTrue(mark.is_visible(), tag + ": mark visible")
        if hint:
            self.assertTrue(page.is_visible(tid("viewport-hint")), tag + ": hint visible")
            self.assertTrue(page.inner_text(tid("viewport-hint")).strip(), tag + ": hint text")

    def test_viewport_ratio_and_brackets(self):
        self.harness.reset()
        for width, height in ((1280, 720), (1366, 768), (1440, 900), (1536, 864)):
            size = "%dx%d" % (width, height)
            page = self.open_page(width, height)
            page.click(tid("history-new"))
            page.wait_for_timeout(150)
            self.check_brackets(page, "empty at " + size, True)
            self.harness.fake.stop()
            try:
                page.evaluate("window.dispatchEvent(new Event('focus'))")
                page.wait_for_selector(tid("comfy-banner"), state="visible", timeout=10000)
                self.check_brackets(page, "down at " + size, False)
            finally:
                self.harness.fake.start()
        status, record = self.harness.post("/api/shots", {**SHOT, "description": "A finished shot for the brackets."})
        self.harness.wait_for_shot(record["id"], "done")
        page = self.open_page(1280, 720)
        page.click(tid("history-item"))
        page.wait_for_timeout(300)
        self.check_brackets(page, "result", False)

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

    def test_aperture_scale_and_iris(self):
        self.harness.reset()
        page = self.open_page(1280, 720)
        self.assertEqual(page.locator(tid("aperture-scale") + " > span").count(), 8)
        slider = page.locator(tid("aperture-slider"))
        slider.focus()
        page.keyboard.press("ArrowRight")
        page.wait_for_function(
            "s => document.querySelector(s).textContent.trim() === 'f/4'", arg=tid("aperture-value")
        )
        self.assertEqual(slider.get_attribute("aria-valuetext"), "f/4")
        page.wait_for_function(
            "s => document.querySelector(s).textContent.includes('f/4')", arg=tid("hud")
        )
        iris_js = (
            "s => { const el = document.querySelector(s);"
            " return [parseFloat(el.style.getPropertyValue('--iris')),"
            " getComputedStyle(el).width]; }"
        )
        values = {}
        for key, index, label in (("min", "0", "f/1.4"), ("max", "7", "f/16")):
            page.fill(tid("aperture-slider"), index)
            page.wait_for_function(
                "([s, t]) => document.querySelector(s).textContent.trim() === t",
                arg=[tid("aperture-value"), label],
            )
            values[key] = page.evaluate(iris_js, tid("aperture-iris"))
        self.assertGreater(values["min"][0], values["max"][0])
        self.assertEqual(values["min"][1], values["max"][1])

    def test_status_panel_centred_and_tracker(self):
        self.harness.reset()
        fake = self.harness.fake
        page = self.open_page(1280, 720)
        panel_sel = tid("status-panel")
        fake.hold_at("SamplerCustomAdvanced")
        try:
            page.locator(tid("shot-description")).fill("A rider crosses a foggy salt flat at dawn.")
            page.locator(tid("generate-button")).click()
            page.wait_for_function(
                "s => document.querySelector(s).dataset.status === 'generating'", arg=panel_sel
            )
            panel = page.locator(panel_sel).bounding_box()
            view = page.locator(tid("viewport")).bounding_box()
            self.assertAlmostEqual(
                panel["x"] + panel["width"] / 2, view["x"] + view["width"] / 2, delta=40
            )
            self.assertAlmostEqual(
                panel["y"] + panel["height"] / 2, view["y"] + view["height"] / 2, delta=40
            )
            self.assertEqual(page.locator(tid("stage-generate")).get_attribute("data-state"), "active")
            self.assertEqual(page.locator(tid("stage-optics")).get_attribute("data-state"), "pending")
            content = page.evaluate(
                "s => getComputedStyle(document.querySelector(s), '::before').content",
                tid("stage-generate"),
            )
            self.assertNotIn(content, ("none", ""))
            self.assertRegex(page.locator(tid("elapsed")).text_content(), r"^\d+:\d{2}$")
            self.assertRegex(page.locator(tid("progress-bar")).get_attribute("aria-valuenow"), r"^\d+$")
            self.assertTrue(page.locator(tid("cancel-button")).is_visible())
        finally:
            fake.release()

    def test_status_panel_failed_tracker(self):
        self.harness.reset()
        fake = self.harness.fake
        fake.clear_failures()
        self.addCleanup(fake.clear_failures)
        message = "Out of memory in Depth of Field"
        fake.fail("OpenOptics_DepthOfField", message)
        page = self.open_page(1280, 720)
        page.locator(tid("shot-description")).fill("A rider crosses a foggy salt flat at dawn.")
        page.locator(tid("generate-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'failed'",
            arg=tid("viewport"),
        )
        self.assertEqual(page.locator(tid("stage-generate")).get_attribute("data-state"), "done")
        self.assertEqual(page.locator(tid("stage-optics")).get_attribute("data-state"), "failed")
        error = page.locator(tid("error-message"))
        self.assertTrue(error.is_visible())
        self.assertIn(message, error.inner_text())
        retry = page.locator(tid("retry-button"))
        self.assertTrue(retry.is_visible())
        self.assertEqual(retry.inner_text().strip(), "Retry optics")
        self.assertFalse(page.locator(tid("cancel-button")).is_visible())

    def test_header(self):
        page = self.open_page(1280, 720)
        height = page.evaluate("() => document.querySelector('header').getBoundingClientRect().height")
        self.assertGreaterEqual(height, 48)
        self.assertLessEqual(height, 56)
        self.assertIn("Open Cinema", page.inner_text("header"))
        self.assertEqual(page.locator(tid("logo-mark")).count(), 1)
        self.assertEqual(page.evaluate("s => document.querySelector(s).tagName.toLowerCase()", tid("logo-mark")), "svg")
        self.assertEqual(page.locator("header img").count(), 0)

    def test_accessible_names(self):
        page = self.open_page(1280, 720)
        page.wait_for_selector(tid("generate-button"))
        controls = page.evaluate(
            """() => {
                const text = el => (el.textContent || '').trim();
                const nameOf = el => {
                    const label = (el.getAttribute('aria-label') || '').trim();
                    if (label) return label;
                    const ids = (el.getAttribute('aria-labelledby') || '').split(/\\s+/).filter(Boolean);
                    const by = ids.map(id => document.getElementById(id)).filter(Boolean).map(text).join(' ').trim();
                    if (by) return by;
                    const labels = el.labels ? Array.from(el.labels).map(text).join(' ').trim() : '';
                    if (labels) return labels;
                    return el.tagName.toLowerCase() === 'button' ? text(el) : '';
                };
                return Array.from(document.querySelectorAll('button, input, select, textarea, [role=slider]'))
                    .filter(el => el.type !== 'hidden' && getComputedStyle(el).display !== 'none'
                        && (el.offsetParent !== null || el.getClientRects().length > 0))
                    .map(el => ({
                        tag: el.tagName.toLowerCase(),
                        testid: el.getAttribute('data-testid') || '',
                        name: nameOf(el),
                    }));
            }"""
        )
        self.assertTrue(controls)
        for control in controls:
            self.assertTrue(
                control["name"],
                "no accessible name: <%s> data-testid=%r" % (control["tag"], control["testid"]),
            )

    def test_status_pill_connected(self):
        page = self.open_page(1280, 720)
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).textContent.trim().startsWith('ComfyUI: connected')",
            arg=tid("comfy-status"),
        )
        color = page.evaluate(
            "s => getComputedStyle(document.querySelector(s), '::before').backgroundColor",
            tid("comfy-status"),
        )
        self.assertEqual(color, "rgb(90, 209, 154)")

    def test_status_pill_contrast(self):
        page = self.open_page(1280, 720)
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).textContent.trim().startsWith('ComfyUI: connected')",
            arg=tid("comfy-status"),
        )
        ratio = page.evaluate(
            """s => {
                const parse = c => c.match(/[\\d.]+/g).map(Number);
                const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
                const lum = c => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
                const el = document.querySelector(s);
                const fg = parse(getComputedStyle(el).color);
                let node = el;
                let bg = parse(getComputedStyle(node).backgroundColor);
                while ((bg.length > 3 ? bg[3] : 1) === 0 && node.parentElement) {
                    node = node.parentElement;
                    bg = parse(getComputedStyle(node).backgroundColor);
                }
                const a = lum(fg), b = lum(bg);
                return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
            }""",
            tid("comfy-status"),
        )
        self.assertGreaterEqual(ratio, 4.5)

    def test_status_pill_offline(self):
        self.addCleanup(self.harness.fake.start)
        self.harness.fake.stop()
        page = self.open_page(1280, 720)
        page.evaluate("window.dispatchEvent(new Event('focus'))")
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).textContent.includes('ComfyUI: offline')",
            arg=tid("comfy-status"),
        )
        color = page.evaluate(
            "s => getComputedStyle(document.querySelector(s), '::before').backgroundColor",
            tid("comfy-status"),
        )
        self.assertEqual(color, "rgb(255, 107, 107)")

    def test_player_transport_bar(self):
        self.harness.reset()
        page = self.open_page(1280, 720)
        page.locator(tid("shot-description")).fill("A rider crosses a foggy salt flat at dawn.")
        page.locator(tid("generate-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )
        page.wait_for_function(
            "() => { const t = document.querySelector('[data-testid=play-toggle]');"
            " return !!t && !t.disabled; }"
        )
        controls = page.locator(tid("player-controls"))
        self.assertTrue(controls.is_visible())
        top = controls.bounding_box()["y"]
        view = page.locator(tid("viewport")).bounding_box()
        self.assertGreaterEqual(top, view["y"] + view["height"] - 1)

        toggle = page.locator(tid("play-toggle"))
        self.assertEqual(toggle.get_attribute("aria-pressed"), "false")
        self.assertEqual(toggle.get_attribute("aria-label"), "Play")
        toggle.click()
        page.wait_for_function(
            "() => { const t = document.querySelector('[data-testid=play-toggle]');"
            " return t.getAttribute('aria-pressed') === 'true' && t.getAttribute('aria-label') === 'Pause'"
            " && !document.querySelector('[data-testid=before-video]').paused; }"
        )
        toggle.click()
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every("
            "n => document.querySelector('[data-testid=' + n + ']').paused === true)"
        )

        page.evaluate(
            "() => { const v = document.querySelector('[data-testid=before-video]');"
            " window.__t0 = v.currentTime; const s = document.querySelector('[data-testid=scrubber]');"
            " s.value = (Number(s.value) > 500) ? 100 : 900;"
            " s.dispatchEvent(new Event('input', {bubbles: true})); }"
        )
        page.wait_for_function(
            "() => Math.abs(document.querySelector('[data-testid=before-video]').currentTime"
            " - window.__t0) > 0.05"
        )
        self.assertRegex(page.inner_text(tid("time-readout")), r"^\d+:\d\d / \d+:\d\d$")

        page.keyboard.press("Shift")
        toggle.focus()
        outline = page.evaluate(
            "s => getComputedStyle(document.querySelector(s)).outlineColor", tid("play-toggle")
        )
        accent = page.evaluate(
            """() => {
                const probe = document.createElement('span');
                probe.style.color = getComputedStyle(document.documentElement).getPropertyValue('--accent');
                document.body.appendChild(probe);
                const c = getComputedStyle(probe).color;
                probe.remove();
                return c;
            }"""
        )
        self.assertEqual(outline, accent)

        size = page.viewport_size
        for name in ("hud", "label-before"):
            box = page.locator(tid(name)).bounding_box()
            self.assertGreaterEqual(box["x"], 0, name)
            self.assertGreaterEqual(box["y"], 0, name)
            self.assertLessEqual(box["x"] + box["width"], size["width"], name)
            self.assertLessEqual(box["y"] + box["height"], size["height"], name)

    def test_lens_figure_and_distance(self):
        self.harness.reset()
        page = self.open_page(1280, 720)
        metres = {}
        framing = page.get_attribute(tid("framing-group") + " [aria-checked=true]", "data-value")
        for lens in (24, 35, 50, 85):
            expected = page.evaluate(
                "async ([l, f]) => (await (await fetch('/api/estimate?lens_mm=' + l"
                " + '&framing=' + f)).json()).subject_distance_m",
                [lens, framing],
            )
            page.click("%s [data-value='%d']" % (tid("lens-group"), lens))
            page.wait_for_function(
                "([s, d, n, e]) => document.querySelector(s).textContent.trim() === n"
                " && Number(document.querySelector(d).getAttribute('data-metres')) === e",
                arg=[
                    tid("lens-figure") + " .lens-figure-num",
                    tid("subject-distance"),
                    str(lens),
                    expected,
                ],
            )
            metres[lens] = page.get_attribute(tid("subject-distance"), "data-metres")
        self.assertNotEqual(metres[24], metres[85])

    def test_lens_checked_and_keyboard(self):
        self.harness.reset()
        page = self.open_page(1280, 720)
        group = tid("lens-group")
        figure = tid("lens-figure") + " .lens-figure-num"
        checked = group + " [aria-checked=true]"

        def wait_figure(text):
            page.wait_for_function(
                "([s, t]) => document.querySelector(s).textContent.trim() === t",
                arg=[figure, text],
            )

        page.click("%s [data-value='50']" % group)
        wait_figure("50")
        self.assertEqual(page.locator(checked).count(), 1)
        self.assertEqual(page.locator(checked).inner_text().strip(), "50 mm")

        accent = page.evaluate(
            """() => {
                const probe = document.createElement('span');
                probe.style.color = 'var(--accent)';
                document.body.appendChild(probe);
                const c = getComputedStyle(probe).color;
                probe.remove();
                return c;
            }"""
        )
        border = "s => getComputedStyle(document.querySelector(s)).borderBottomColor"
        self.assertEqual(page.evaluate(border, checked), accent)
        self.assertNotEqual(page.evaluate(border, "%s [data-value='24']" % group), accent)

        page.focus(checked)
        page.keyboard.press("ArrowRight")
        wait_figure("85")
        self.assertEqual(page.locator(checked).count(), 1)
        page.keyboard.press("ArrowLeft")
        wait_figure("50")
        self.assertEqual(page.locator(checked).count(), 1)
        self.assertEqual(page.locator(checked).inner_text().strip(), "50 mm")


if __name__ == "__main__":
    unittest.main()
