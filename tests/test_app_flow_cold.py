"""Browser flow test: the app started while ComfyUI is not running shows the banner and a disabled Generate button."""
from __future__ import annotations

import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness
from tests.fake_comfy import FakeComfy


class ColdStartFlowTest(unittest.TestCase):
    harness = None
    fake = None
    playwright = None
    browser = None
    page = None

    @classmethod
    def setUpClass(cls):
        try:
            cls.fake = FakeComfy(delay=0.03)
            cls.fake.start()
            cls.comfy_port = cls.fake._port
            cls.fake.stop()
            cls.harness = AppHarness(fake=cls.fake)
            cls.harness.start_app()
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch(headless=True)
            cls.page = cls.browser.new_page(viewport={"width": 1366, "height": 768})
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for close in (
            lambda: cls.page.close(),
            lambda: cls.browser.close(),
            lambda: cls.playwright.stop(),
            lambda: cls.harness.stop(),
            lambda: cls.fake.close(),
        ):
            try:
                close()
            except Exception:
                pass

    def test_1_cold_start(self):
        harness, port, page = self.harness, self.comfy_port, self.page
        self.assertIn(
            f"Open Cinema is running at http://127.0.0.1:{harness.port} (ComfyUI at http://127.0.0.1:{port})",
            harness.log(),
        )
        page.goto(harness.url)
        page.wait_for_function(
            "() => { const e = document.querySelector('[data-testid=comfy-status]'); return e && e.getAttribute('data-state') === 'down'; }",
            timeout=10000,
        )
        banner = page.locator("[data-testid=comfy-banner]")
        self.assertEqual(banner.count(), 1)
        self.assertTrue(banner.is_visible())
        self.assertIn(f"Can't reach ComfyUI at http://127.0.0.1:{port}", banner.inner_text())
        page.locator("[data-testid=shot-description]").fill("A lighthouse keeper climbs the stairs at dawn.")
        self.assertTrue(page.locator("[data-testid=generate-button]").is_disabled())


if __name__ == "__main__":
    unittest.main()
