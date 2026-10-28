import unittest
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class DownloadMediaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def _fetch(self, url):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_download_query_sets_attachment_header(self):
        h = self.harness
        h.reset()
        status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
        self.assertEqual(status, 201)
        sid = created["id"]
        try:
            record = h.wait_for_shot(sid, "done")
        except AssertionError as e:
            raise AssertionError(f"{e}\n{h.log()}") from None
        if not isinstance(record, dict):
            record = h.get(f"/api/shots/{sid}")[1]
        media = record["versions"][0]["url"]
        name = media.rsplit("/", 1)[1]
        url = h.url + media

        status, headers, plain = self._fetch(url)
        self.assertEqual(status, 200)
        self.assertIsNone(headers["Content-Disposition"])

        status, headers, body = self._fetch(url + "?download=1")
        self.assertEqual(status, 200)
        self.assertEqual(body, plain)
        self.assertEqual(headers["Content-Disposition"], f'attachment; filename="opencinema-{sid}-{name}"')

        status, headers, body = self._fetch(f"{h.url}/media/{sid}/missing.mp4?download=1")
        self.assertEqual(status, 404)
        self.assertIn(b"not_found", body)
        self.assertIsNone(headers["Content-Disposition"])


class DownloadLinkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = cls.browser = cls.harness = None
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

    def test_link_follows_shown_version(self):
        h = self.harness
        h.reset()
        status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
        self.assertEqual(status, 201)
        sid = created["id"]
        h.wait_for_shot(sid, "done")
        status, _ = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
        self.assertIn(status, (200, 202))
        h.wait_until(
            sid,
            lambda r: r["status"] == "done" and len(r["versions"]) == 2,
            what="two versions",
        )
        versions = h.get(f"/api/shots/{sid}")[1]["versions"]

        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.goto(h.url)
        page.wait_for_function(
            "() => { const v = document.querySelector('[data-testid=viewport]');"
            " return !!v && v.dataset.state === 'result'; }"
        )
        link = page.locator("[data-testid=download-link]")
        link.wait_for(state="visible")
        self.assertEqual(link.evaluate("e => e.tagName"), "A")
        self.assertIsNotNone(link.get_attribute("download"))
        self.assertEqual(link.text_content().strip(), "Download")
        self.assertEqual(link.get_attribute("aria-label"), "Download the f/8 version")
        self.assertTrue(link.get_attribute("href").endswith(versions[-1]["url"] + "?download=1"))
        self.assertGreaterEqual(link.bounding_box()["height"], 32)

        page.locator("[data-testid=version-chip]").first.click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=download-link]')"
            ".getAttribute('aria-label') === 'Download the f/2.8 version'"
        )
        href = link.get_attribute("href")
        self.assertTrue(href.endswith(versions[0]["url"] + "?download=1"))
        with urllib.request.urlopen(h.url + href, timeout=15) as r:
            self.assertEqual(r.status, 200)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
