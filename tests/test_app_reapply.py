import time
import unittest
import urllib.request

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy

GENERATION = ("SamplerCustomAdvanced", "VAEDecodeTiled")
DEPTH = ("DA3Inference", "OpenOptics_DepthToMetric")
OPTICS = ("OpenOptics_DepthOfField", "CreateVideo", "SaveVideo")


class ReapplyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_reapply_reuses_cached_depth(self):
        h, fake = self.harness, self.fake
        status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
        self.assertEqual(status, 201)
        sid = created["id"]
        try:
            h.wait_for_shot(sid, "done")
        except AssertionError as e:
            raise AssertionError(f"{e}\n{h.log()}") from None
        before = {c: fake.count(c) for c in GENERATION + DEPTH + OPTICS}

        status, body = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
        self.assertEqual(status, 202)
        self.assertEqual(body["status"], "optics")

        seen = []
        stage_states = []
        deadline = time.time() + 60
        record = body
        while time.time() < deadline:
            code, record = h.get(f"/api/shots/{sid}")
            self.assertEqual(code, 200)
            seen.append(record["progress"])
            stage_states.append(record["stages"][0]["state"])
            if record["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.02)
        else:
            self.fail(f"re-apply did not finish; last record: {record}")
        self.assertEqual(record["status"], "done", h.log())

        self.assertEqual([v["n"] for v in record["versions"]], [1, 2])
        self.assertEqual(record["current_version"], 2)
        version = record["versions"][1]
        self.assertEqual(version["aperture"], 8)
        with urllib.request.urlopen(h.url + version["url"], timeout=15) as r:
            self.assertEqual(r.status, 200)

        for c in GENERATION + DEPTH:
            self.assertEqual(fake.count(c), before[c], c)
        for c in OPTICS:
            self.assertEqual(fake.count(c), before[c] + 1, c)
        self.assertEqual(seen, sorted(seen))
        self.assertEqual(set(stage_states), {"done"})


if __name__ == "__main__":
    unittest.main()
