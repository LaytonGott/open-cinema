"""Browser test that every control in the empty state has an accessible name."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

NAMES_JS = """() => {
  const nameOf = (el) => {
    const label = (el.getAttribute('aria-label') || '').trim();
    if (label) return label;
    const by = el.getAttribute('aria-labelledby');
    if (by) {
      const text = by.split(/\\s+/).map(id => {
        const t = document.getElementById(id);
        return t ? t.textContent.trim() : '';
      }).join(' ').trim();
      if (text) return text;
    }
    if (el.id) {
      const lab = document.querySelector('label[for="' + el.id + '"]');
      if (lab && lab.textContent.trim()) return lab.textContent.trim();
    }
    return (el.textContent || '').trim();
  };
  const hidden = (el) => !el.checkVisibility() || el.type === 'hidden';
  const unnamed = [];
  for (const el of document.querySelectorAll('button, textarea, input, [role=radio]')) {
    if (hidden(el)) continue;
    if (!nameOf(el)) unnamed.push(el.outerHTML.slice(0, 120));
  }
  return unnamed;
}"""


def tid(name):
    return "[data-testid=%s]" % name


class A11yNamesTest(unittest.TestCase):
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

    def test_empty_state_controls_have_names(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)
        page.wait_for_selector(tid("camera-group") + " [role=radio]")
        self.assertEqual(page.evaluate(NAMES_JS), [])
        for group in ("camera-group", "lens-group", "framing-group"):
            label = page.locator(tid(group)).get_attribute("aria-label")
            self.assertTrue(label and label.strip(), group + " has no aria-label")


if __name__ == "__main__":
    unittest.main()
