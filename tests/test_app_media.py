import json
import unittest
import urllib.error
import urllib.request

from tests.app_harness import SHOT, AppHarness


def fetch(harness, path, headers=None):
    """GET ``path``; return (status, headers, body) without parsing the body."""
    req = urllib.request.Request(harness.url + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


class MediaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = AppHarness().start()
        status, shot = cls.harness.post("/api/shots", SHOT)
        assert status in (200, 201, 202), (status, shot)
        cls.shot_id = shot["id"]
        cls.record = cls.harness.wait_for_shot(cls.shot_id, "done")

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()

    def urls(self):
        return [self.record["before_url"], self.record["versions"][0]["url"]]

    def test_full_get(self):
        for url in self.urls():
            status, headers, body = fetch(self.harness, url)
            self.assertEqual(status, 200, url)
            expected = {".webm": "video/webm", ".mp4": "video/mp4"}["." + url.rsplit(".", 1)[1]]
            self.assertEqual(headers.get_content_type(), expected, url)
            self.assertEqual(headers["Accept-Ranges"], "bytes", url)
            on_disk = self.harness.data_dir / "shots" / self.shot_id / url.rsplit("/", 1)[1]
            self.assertEqual(len(body), on_disk.stat().st_size, url)

    def test_range(self):
        for url in self.urls():
            _, _, full = fetch(self.harness, url)
            status, headers, body = fetch(self.harness, url, {"Range": "bytes=0-99"})
            self.assertEqual(status, 206, url)
            self.assertEqual(len(body), 100, url)
            self.assertEqual(body, full[:100], url)
            self.assertEqual(headers["Content-Range"], f"bytes 0-99/{len(full)}", url)

    def test_range_not_satisfiable(self):
        for url in self.urls():
            status, _, _ = fetch(self.harness, url, {"Range": "bytes=999999999-"})
            self.assertEqual(status, 416, url)

    def test_not_found(self):
        sid = self.shot_id
        for path in (
            f"/media/{sid}/..%2Fshot.json",
            f"/media/{sid}/shot.json%00",
            f"/media/{sid}/nope.mp4",
            "/media/unknown-shot-id/before.mp4",
        ):
            status, _, body = fetch(self.harness, path)
            self.assertEqual(status, 404, path)
            self.assertEqual(json.loads(body)["error"]["code"], "not_found", path)


if __name__ == "__main__":
    unittest.main()
