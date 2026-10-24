"""Browser tests that no text is clipped or pushed off screen in the empty and form states."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness


def tid(name):
    return "[data-testid=%s]" % name


CLIPPED_JS = """
() => {
  const roots = document.querySelectorAll('header, #director, #monitor, [data-testid=hud], #history');
  const seen = new Set();
  const out = [];
  const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
  const describe = el => el.tagName.toLowerCase() +
    (el.dataset.testid ? '[' + el.dataset.testid + ']' : '') +
    ' "' + (el.textContent || '').trim().slice(0, 40) + '"';
  const visible = el => {
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
  };
  for (const root of roots) {
    for (const el of [root, ...root.querySelectorAll('*')]) {
      if (seen.has(el) || !visible(el)) continue;
      seen.add(el);
      const s = getComputedStyle(el);
      const hasText = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      if (hasText && el.scrollWidth > el.clientWidth + 1 && !/auto|scroll/.test(s.overflowX)) {
        out.push('clipped: ' + describe(el));
      }
      if (el.matches('button, label, .chip, [class*=chip]')) {
        const r = el.getBoundingClientRect();
        if (r.left < -1 || r.top < -1 || r.right > vw + 1 || r.bottom > vh + 1) {
          out.push('outside viewport: ' + describe(el));
        }
      }
    }
  }
  return out;
}
"""


def clipped_elements(page):
    """Return descriptions of clipped single-line text and of controls outside the viewport."""
    return page.evaluate(CLIPPED_JS)


OVERLAP_PAIRS = (
    ("generate-button vs history-list", tid("generate-button"), tid("history-list")),
    ("hud vs status-panel", tid("hud"), tid("status-panel")),
    ("app name vs comfy-status", "header h1", tid("comfy-status")),
)

OVERLAPS_JS = """
(pairs) => {
  const box = sel => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    if (s.display === 'none' || s.visibility === 'hidden' || r.width <= 0 || r.height <= 0) return null;
    return r;
  };
  const out = [];
  for (const [name, a, b] of pairs) {
    const ra = box(a), rb = box(b);
    if (!ra || !rb) continue;
    if (ra.left < rb.right && rb.left < ra.right && ra.top < rb.bottom && rb.top < ra.bottom) out.push(name);
  }
  return out;
}
"""


def overlaps(page):
    """Return the names of element pairs whose bounding boxes intersect; a pair with a missing or hidden element is skipped."""
    return page.evaluate(OVERLAPS_JS, [list(p) for p in OVERLAP_PAIRS])


class VisualReviewTest(unittest.TestCase):
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

    def test_no_clipping_empty_and_form(self):
        for width, height in ((1280, 720), (1366, 768)):
            page = self.browser.new_page(viewport={"width": width, "height": height})
            self.addCleanup(page.close)
            page.set_default_timeout(15000)
            page.goto(self.harness.url)
            page.wait_for_selector(tid("generate-button"))
            page.click(tid("history-new"))
            self.assertEqual(clipped_elements(page), [], "empty %dx%d" % (width, height))
            page.fill(
                tid("shot-description"),
                "A woman in a red coat walks slowly through a rainy neon street at night.",
            )
            self.assertEqual(clipped_elements(page), [], "form %dx%d" % (width, height))

    def test_no_overlaps_working(self):
        fake = self.harness.fake
        for width, height in ((1280, 720), (1366, 768)):
            self.harness.reset()
            page = self.browser.new_page(viewport={"width": width, "height": height})
            self.addCleanup(page.close)
            page.set_default_timeout(15000)
            page.goto(self.harness.url)
            page.wait_for_selector(tid("generate-button"))
            page.click(tid("history-new"))
            page.fill(tid("shot-description"), "A woman in a red coat crosses a rainy street at night.")
            fake.reset_cache()
            fake.hold_at("SamplerCustomAdvanced")
            try:
                page.click(tid("generate-button"))
                page.wait_for_selector(tid("viewport") + "[data-state=working]")
                self.assertEqual(clipped_elements(page), [], "working %dx%d" % (width, height))
                self.assertEqual(overlaps(page), [], "working %dx%d" % (width, height))
            finally:
                fake.release()

    def test_no_overlaps_result(self):
        fake = self.harness.fake
        for width, height in ((1280, 720), (1366, 768)):
            self.harness.reset()
            page = self.browser.new_page(viewport={"width": width, "height": height})
            self.addCleanup(page.close)
            page.set_default_timeout(15000)
            page.goto(self.harness.url)
            page.wait_for_selector(tid("generate-button"))
            page.click(tid("history-new"))
            page.fill(tid("shot-description"), "A woman in a red coat crosses a rainy street at night.")
            fake.reset_cache()
            fake.hold_at("SamplerCustomAdvanced")
            try:
                page.click(tid("generate-button"))
                page.wait_for_selector(tid("viewport") + "[data-state=working]")
                fake.release()
                page.wait_for_selector(tid("viewport") + "[data-state=result]")
                label = "result %dx%d" % (width, height)
                self.assertEqual(clipped_elements(page), [], label)
                self.assertEqual(overlaps(page), [], label)
                boxes = [page.locator(tid(n)).bounding_box() for n in ("label-before", "label-after", "compare-handle")]
                for i in range(len(boxes)):
                    self.assertIsNotNone(boxes[i], label)
                    for j in range(i + 1, len(boxes)):
                        a, b = boxes[i], boxes[j]
                        apart = (
                            a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
                            or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"]
                        )
                        self.assertTrue(apart, "%s boxes %d and %d intersect" % (label, i, j))
            finally:
                fake.release()

    def test_no_overlaps_failed(self):
        fake = self.harness.fake
        for width, height in ((1280, 720), (1366, 768)):
            self.harness.reset()
            page = self.browser.new_page(viewport={"width": width, "height": height})
            self.addCleanup(page.close)
            page.set_default_timeout(15000)
            page.goto(self.harness.url)
            page.wait_for_selector(tid("generate-button"))
            page.click(tid("history-new"))
            page.fill(tid("shot-description"), "A woman in a red coat crosses a rainy street at night.")
            fake.reset_cache()
            fake.fail("OpenOptics_DepthOfField", "Out of memory in Depth of Field")
            try:
                page.click(tid("generate-button"))
                page.wait_for_selector(tid("viewport") + "[data-state=failed]")
                label = "failed %dx%d" % (width, height)
                self.assertEqual(clipped_elements(page), [], label)
                self.assertEqual(overlaps(page), [], label)
            finally:
                fake.clear_failures()
