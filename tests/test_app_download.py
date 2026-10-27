import unittest
import urllib.error
import urllib.request

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


if __name__ == "__main__":
    unittest.main()
