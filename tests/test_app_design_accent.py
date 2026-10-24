"""Browser test that amber (--accent) shows only on the allowed surfaces in the idle empty state."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"

JS_OFFENDERS = """() => {
  const probe = document.createElement('span');
  probe.style.color = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
  document.body.appendChild(probe);
  const accent = getComputedStyle(probe).color;
  probe.remove();
  const allowed = '[data-testid=generate-button], [aria-pressed=true], [aria-checked=true], [aria-selected=true], .selected, :checked';
  const label = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
    + [...el.classList].map(c => '.' + c).join('')
    + (el.getAttribute('data-testid') ? '[data-testid=' + el.getAttribute('data-testid') + ']' : '');
  const out = [];
  for (const el of document.body.querySelectorAll('*')) {
    const s = getComputedStyle(el);
    const b = el.getBoundingClientRect();
    if (s.display === 'none' || s.visibility === 'hidden' || b.width === 0 || b.height === 0) continue;
    if (el.closest(allowed) || el.matches(':focus, :focus-visible') || el.closest('label:has(:checked)')) continue;
    const props = [];
    if (s.backgroundColor === accent) props.push('background-color');
    if (s.color === accent) props.push('color');
    for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
      if (s['border' + side + 'Color'] === accent && parseFloat(s['border' + side + 'Width']) > 0
          && s['border' + side + 'Style'] !== 'none') { props.push('border-' + side.toLowerCase() + '-color'); }
    }
    if (props.length) out.push(label(el) + ' ' + props.join(','));
  }
  return out;
}"""


class AccentSurfacesTest(unittest.TestCase):
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
        self.page.goto(self.harness.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )
        self.page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'empty'"
        )
        self.page.evaluate("() => document.activeElement && document.activeElement.blur()")

    def test_amber_only_on_allowed_surfaces(self):
        offenders = self.page.evaluate(JS_OFFENDERS)
        self.assertEqual(offenders, [], "amber used outside the allowed surfaces: %s" % offenders)


if __name__ == "__main__":
    unittest.main()
