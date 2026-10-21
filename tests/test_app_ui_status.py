"""Browser test of the header ComfyUI status (data-testid=comfy-status)."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

SEL = "[data-testid=comfy-status]"


class _StatusBase(unittest.TestCase):
    harness = None
    pw = None
    browser = None

    @classmethod
    def prepare(cls, h):
        pass

    @classmethod
    def setUpClass(cls):
        try:
            cls.harness = AppHarness().start()
            cls.prepare(cls.harness)
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

    def open_page(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(self.harness.url)
        return page


class HeaderStatusConnectedTest(_StatusBase):
    def test_connected(self):
        page = self.open_page()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=SEL
        )
        text = page.locator(SEL).inner_text()
        self.assertIn("ComfyUI: connected", text)
        self.assertIn("3090", text)


class HeaderStatusOfflineTest(_StatusBase):
    @classmethod
    def prepare(cls, h):
        h.fake.stop()

    def test_offline(self):
        page = self.open_page()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'down'", arg=SEL
        )
        self.assertIn("ComfyUI: offline", page.locator(SEL).inner_text())


if __name__ == "__main__":
    unittest.main()
