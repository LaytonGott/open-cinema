import unittest
import urllib.request

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy

RECORD_KEYS = {
    "id", "created_at", "params", "derived", "status", "progress", "message", "stages",
    "elapsed_s", "error", "reapply_error", "before_url", "versions", "current_version",
}


class BackendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = AppHarness(fake=FakeComfy()).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()

    def test_create_shot(self):
        status, record = self.harness.post("/api/shots", SHOT)
        self.assertEqual(status, 201)
        self.assertRegex(record["id"], r"^\d{8}-\d{6}-[0-9a-f]{4}$")
        self.assertEqual(record["status"], "queued")
        self.assertEqual(set(record), RECORD_KEYS)
        self.assertEqual(record["params"]["seed"], 7)

    def test_invalid_shot(self):
        status, body = self.harness.post("/api/shots", {"description": "x"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_shot")
        status, body = self.harness.post("/api/shots", [1])
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_shot")

    def test_list_newest_first(self):
        ids = [self.harness.post("/api/shots", SHOT)[1]["id"] for _ in range(3)]
        status, first = self.harness.get("/api/shots")
        self.assertEqual(status, 200)
        self.assertEqual([s["id"] for s in first["shots"]][:3], ids[::-1])
        for record in first["shots"]:
            self.assertEqual(set(record), RECORD_KEYS)
            self.assertNotIn("seq", record)
        self.assertEqual(self.harness.get("/api/shots"), (200, first))

    def test_get_shot(self):
        created = self.harness.post("/api/shots", SHOT)[1]
        status, record = self.harness.get("/api/shots/" + created["id"])
        self.assertEqual(status, 200)
        self.assertEqual(record["id"], created["id"])
        self.assertEqual(set(record), RECORD_KEYS)

    def test_not_found(self):
        status, body = self.harness.get("/api/shots/19990101-000000-abcd")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertTrue(body["error"]["message"])
        status, body = self.harness.get("/api/nothing-here")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertNotIn("Traceback", str(body))

    def test_media_range(self):
        created = self.harness.post("/api/shots", SHOT)[1]
        folder = self.harness.data_dir / "shots" / created["id"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "clip.webm").write_bytes(b"0123456789")
        url = f"{self.harness.url}/media/{created['id']}/clip.webm"
        with urllib.request.urlopen(url, timeout=15) as r:
            self.assertEqual(r.status, 200)
            self.assertEqual(r.headers["Content-Type"], "video/webm")
            self.assertEqual(r.read(), b"0123456789")
        req = urllib.request.Request(url, headers={"Range": "bytes=0-3"})
        with urllib.request.urlopen(req, timeout=15) as r:
            self.assertEqual(r.status, 206)
            self.assertEqual(r.read(), b"0123")
        status, body = self.harness.get(f"/media/{created['id']}/missing.webm")
        self.assertEqual((status, body["error"]["code"]), (404, "not_found"))
        status, body = self.harness.get(f"/media/{created['id']}/..%2Frecord.json")
        self.assertEqual((status, body["error"]["code"]), (404, "not_found"))
        status, body = self.harness.get(f"/media/{created['id']}/..")
        self.assertEqual((status, body["error"]["code"]), (404, "not_found"))
        status, body = self.harness.get("/media/19990101-000000-abcd/clip.webm")
        self.assertEqual((status, body["error"]["code"]), (404, "not_found"))


if __name__ == "__main__":
    unittest.main()
