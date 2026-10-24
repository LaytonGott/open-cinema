"""Browser test of the text contrast (WCAG ratio >= 4.5) in the empty, filled, result and failed states."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import SHOT, AppHarness

STATUS = "[data-testid=comfy-status]"
MIN_RATIO = 4.5

JS_CONTRAST = """() => {
  const parse = c => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const blend = (top, bottom) => ({r: top.r * top.a + bottom.r * (1 - top.a), g: top.g * top.a + bottom.g * (1 - top.a), b: top.b * top.a + bottom.b * (1 - top.a), a: 1});
  const bgOf = el => { const layers = []; for (let e = el; e; e = e.parentElement) { const s = getComputedStyle(e); if (s.backgroundImage !== 'none') return null; const c = parse(s.backgroundColor); if (c && c.a > 0) { layers.push(c); if (c.a >= 0.999) break; } }
    let base = {r: 255, g: 255, b: 255, a: 1}; for (let i = layers.length - 1; i >= 0; i--) base = blend(layers[i], base); return base; };
  const ratioOf = (fg, bg) => { const l1 = lum(fg) + 0.05, l2 = lum(bg) + 0.05; return Math.round(Math.max(l1, l2) / Math.min(l1, l2) * 100) / 100; };
  const probe = document.createElement('span'); probe.style.color = 'var(--muted)'; document.body.appendChild(probe);
  const muted = getComputedStyle(probe).color; probe.remove();
  const testidOf = el => (el.closest('[data-testid]') || {getAttribute: () => null}).getAttribute('data-testid');
  const out = [];
  const skip = e => e.closest('[data-testid="hud"], [data-testid="player"] [data-testid="label-before"], [data-testid="player"] [data-testid="label-after"], video');
  const hidden = (el, s, b) => s.display === 'none' || s.visibility === 'hidden' || b.width === 0 || b.height === 0 || el.closest('[disabled]') || el.closest('[aria-disabled="true"]');
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode; if (!t.textContent.trim()) continue; const el = t.parentElement; if (!el || seen.has(el) || skip(el)) continue; seen.add(el);
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    if (hidden(el, s, b) || ['SCRIPT', 'STYLE', 'TITLE'].includes(el.tagName)) continue;
    const bg = bgOf(el); if (!bg) continue; let fg = parse(s.color); if (!fg) continue;
    fg = blend({...fg, a: fg.a * parseFloat(s.opacity || 1)}, bg);
    out.push({kind: 'text', text: t.textContent.trim().slice(0, 40), testid: testidOf(el), ratio: ratioOf(fg, bg),
              muted: s.color === muted, history: !!el.closest('[data-testid="history-item"]')});
  }
  for (const el of document.querySelectorAll('input[placeholder], textarea[placeholder]')) {
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    if (hidden(el, s, b) || skip(el) || el.value) continue;
    const bg = bgOf(el); if (!bg) continue; let fg = parse(getComputedStyle(el, '::placeholder').color); if (!fg) continue;
    fg = blend(fg, bg);
    out.push({kind: 'placeholder', text: el.getAttribute('placeholder').slice(0, 40), testid: testidOf(el), ratio: ratioOf(fg, bg), muted: false, history: false});
  }
  return out;
}"""

JS_BACKGROUND_IMAGES = """() => {
  const bad = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode; const el = t.parentElement;
    if (!t.textContent.trim() || !el || seen.has(el) || el.closest('video, [data-testid="hud"]')) continue;
    seen.add(el);
    const b = el.getBoundingClientRect(); const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || b.width === 0 || b.height === 0) continue;
    for (let e = el; e; e = e.parentElement) {
      if (getComputedStyle(e).backgroundImage !== 'none') { bad.push(t.textContent.trim().slice(0, 40) + ' <- ' + e.tagName + '.' + e.className); break; }
    }
  }
  return bad;
}"""


class ContrastTest(unittest.TestCase):
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

    def open(self):
        self.page.goto(self.harness.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def wait_viewport(self, state):
        self.page.wait_for_function(
            "s => document.querySelector('[data-testid=viewport]').dataset.state === s", arg=state, timeout=40000
        )

    def make_result(self):
        status, record = self.harness.post("/api/shots", SHOT)
        self.assertEqual(status, 201)
        self.harness.wait_for_shot(record["id"], "done")
        self.open()
        self.page.locator("[data-testid=history-item]").first.click()
        self.wait_viewport("result")
        self.page.wait_for_timeout(300)

    def scan(self):
        # let colour transitions (e.g. the Generate button enabling) finish before reading colours
        self.page.evaluate(
            "() => Promise.all(document.getAnimations()"
            ".filter(a => a.effect && a.effect.getTiming().iterations !== Infinity)"
            ".map(a => a.finished.catch(() => null)))"
        )
        return self.page.evaluate(JS_CONTRAST)

    def assert_contrast(self, items, minimum=10):
        low = [r for r in items if r["ratio"] < MIN_RATIO]
        self.assertGreaterEqual(len(items), minimum, "only %d elements scanned" % len(items))
        self.assertFalse(
            low,
            "contrast below %s:1: " % MIN_RATIO
            + "; ".join("%s %r %s" % (r["testid"], r["text"], r["ratio"]) for r in low),
        )

    def test_empty_state(self):
        self.open()
        self.wait_viewport("empty")
        self.assert_contrast(self.scan())

    def test_filled_form(self):
        self.open()
        self.wait_viewport("empty")
        self.page.locator("[data-testid=shot-description]").fill("A woman walks through a rainy street at night")
        self.assert_contrast(self.scan())

    def test_result_state(self):
        self.make_result()
        self.assert_contrast(self.scan())

    def test_failed_state(self):
        fake = self.harness.fake
        self.addCleanup(fake.clear_failures)
        fake.reset_cache()
        fake.fail("OpenOptics_DepthOfField", "Out of memory in Depth of Field")
        self.open()
        self.wait_viewport("empty")
        self.page.locator("[data-testid=shot-description]").fill("This one fails in optics.")
        self.page.locator("[data-testid=generate-button]").click()
        self.wait_viewport("failed")
        self.assert_contrast(self.scan())

    def test_muted_text_placeholders_and_history_cards(self):
        self.make_result()
        items = self.scan()
        muted = [r for r in items if r["muted"]]
        placeholders = [r for r in items if r["kind"] == "placeholder"]
        cards = [r for r in items if r["history"]]
        self.assertTrue(muted, "no muted text found")
        self.assertTrue(placeholders, "no placeholder found")
        self.assertTrue(cards, "no history card text found")
        self.assert_contrast(items)
        self.assert_contrast(muted + placeholders + cards, minimum=3)

    def assert_solid(self):
        self.assertEqual(self.page.evaluate(JS_BACKGROUND_IMAGES), [], "text over a background-image")
        self.assert_contrast(self.scan())

    def test_history_and_tracker_text_is_solid(self):
        fake = self.harness.fake
        self.make_result()
        self.assertTrue([r for r in self.scan() if r["history"]], "no history card text found")
        self.assert_solid()
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        try:
            self.page.locator("[data-testid=history-new]").click()
            self.page.locator("[data-testid=shot-description]").fill("Held at the sampler for the tracker.")
            self.page.locator("[data-testid=generate-button]").click()
            self.wait_viewport("working")
            for stage in ("stage-generate", "stage-optics"):
                self.page.locator("[data-testid=%s]" % stage).wait_for(state="visible")
            self.assert_solid()
        finally:
            fake.release()
        self.wait_viewport("result")


if __name__ == "__main__":
    unittest.main()
