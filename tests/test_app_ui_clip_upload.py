"""Browser test of "or use your own video": pick a file, only the optics run, the result shows."""
import time
import unittest

from playwright.sync_api import sync_playwright

from app.store import SAMPLES_DIR
from tests.app_harness import AppHarness
from tests.fake_comfy import FakeComfy

CLIP = str(SAMPLES_DIR / "sample-red-coat" / "before.mp4")
GENERATION = ("SamplerCustomAdvanced", "VAEDecodeTiled")


class ClipUploadUiTest(unittest.TestCase):
    fake = harness = pw = browser = None

    @classmethod
    def setUpClass(cls):
        try:
            cls.fake = FakeComfy()
            cls.harness = AppHarness(fake=cls.fake).start()
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
            lambda: cls.fake and cls.fake.close(),
        ):
            try:
                closer()
            except Exception:
                pass
        cls.browser = cls.pw = cls.harness = cls.fake = None

    def test_own_video_gets_the_optics(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(20000)
        page.goto(self.harness.url)
        button = page.locator("[data-testid=import-button]")
        page.wait_for_function("document.querySelector('[data-testid=comfy-status]').dataset.state === 'ok'")
        self.assertTrue(button.is_enabled())
        generated = {c: self.fake.count(c) for c in GENERATION}
        page.set_input_files("[data-testid=import-input]", CLIP)
        page.wait_for_selector('[data-testid="viewport"][data-state="result"]')
        page.wait_for_selector("[data-testid=version-chip]")
        self.assertIn("Imported clip", page.locator("[data-testid=shot-brief] .brief-text").inner_text())
        self.assertNotIn("Static", page.locator("[data-testid=shot-brief] .brief-settings").inner_text())
        self.assertEqual({c: self.fake.count(c) for c in GENERATION}, generated)

    def test_bad_file_shows_an_error(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(20000)
        page.goto(self.harness.url)
        page.wait_for_function("document.querySelector('[data-testid=comfy-status]').dataset.state === 'ok'")
        page.set_input_files("[data-testid=import-input]", {"name": "notes.txt", "mimeType": "text/plain", "buffer": b"hello"})
        page.wait_for_selector("[data-testid=submit-error]:not([hidden])")
        self.assertIn("video", page.locator("[data-testid=submit-error]").inner_text().lower())


if __name__ == "__main__":
    unittest.main()
