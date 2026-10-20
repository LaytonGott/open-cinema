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


def _nodes(graph, class_type):
    return [n for n in graph.values() if n.get("class_type") == class_type]


class FullShotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_full_shot(self):
        h = self.harness
        body = {**SHOT, "seed": 123, "lens_mm": 50, "aperture": 2.8, "framing": "full-body"}
        status, created = h.post("/api/shots", body)
        self.assertEqual(status, 201)
        sid = created["id"]
        try:
            record = h.wait_for_shot(sid, "done")
        except AssertionError as e:
            raise AssertionError(f"{e}\n{h.log()}") from None

        self.assertRegex(record["before_url"], rf"^/media/{sid}/before\.\w+$")
        self.assertEqual(len(record["versions"]), 1)
        version = record["versions"][0]
        self.assertEqual(version["n"], 1)
        self.assertEqual(version["aperture"], 2.8)
        self.assertRegex(version["url"], rf"^/media/{sid}/after_1\.\w+$")
        self.assertTrue(version["created_at"])
        self.assertEqual(record["current_version"], 1)
        self.assertEqual(record["progress"], 1)
        self.assertEqual(record["message"], "Done")

        for url in (record["before_url"], version["url"]):
            with urllib.request.urlopen(h.url + url, timeout=15) as r:
                self.assertEqual(r.status, 200)
                self.assertTrue(r.read())
        folder = h.data_dir / "shots" / sid
        self.assertTrue(list(folder.glob("before.*")))

        derived = record["derived"]
        prompts = list(self.fake.prompts)
        generation = [
            g for g in prompts
            if any(n["inputs"].get("text") == derived["prompt"] for n in _nodes(g, "CLIPTextEncode"))
            and any(n["inputs"].get("noise_seed") == 123 for n in _nodes(g, "RandomNoise"))
            and any(n["inputs"].get("filename_prefix") == f"opencinema/{sid}/before" for n in _nodes(g, "SaveVideo"))
        ]
        self.assertEqual(len(generation), 1)
        optics = [
            g for g in prompts
            if any(n["inputs"].get("filename_prefix") == f"opencinema/{sid}/after_1" for n in _nodes(g, "SaveVideo"))
        ]
        self.assertEqual(len(optics), 1)
        dof = _nodes(optics[0], "OpenOptics_DepthOfField")
        self.assertEqual(len(dof), 1)
        self.assertEqual(dof[0]["inputs"]["focal_mm"], 50)
        self.assertEqual(dof[0]["inputs"]["f_number"], 2.8)
        self.assertAlmostEqual(dof[0]["inputs"]["focus_m"], derived["subject_distance_m"], places=3)


if __name__ == "__main__":
    unittest.main()
