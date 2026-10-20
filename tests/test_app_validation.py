import json
import unittest
import urllib.error
import urllib.request

from tests.app_harness import SHOT, AppHarness


class ShotValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = AppHarness().start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()

    def _raw_post(self, raw):
        req = urllib.request.Request(self.harness.url + "/api/shots", data=raw, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def _assert_invalid(self, status, body, field):
        self.assertEqual(status, 400, body)
        error = body["error"]
        self.assertEqual(error["code"], "invalid_shot")
        self.assertEqual(error["field"], field)
        self.assertIsInstance(error["message"], str)
        self.assertTrue(error["message"].strip())

    def test_invalid_bodies_are_rejected_and_nothing_is_stored(self):
        _, before = self.harness.get("/api/shots")
        cases = [
            ("description", "ab"),
            ("description", "   a  "),
            ("description", "x" * 1001),
            ("camera", "zoom"),
            ("lens_mm", 30),
            ("aperture", 3),
            ("framing", "huge"),
            ("seed", -1),
            ("seed", 2147483648),
            ("seed", "x"),
        ]
        cases += [(name, None) for name in ("description", "camera", "lens_mm", "aperture", "framing")]
        for field, value in cases:
            with self.subTest(field=field, value=str(value)[:20]):
                status, body = self.harness.post("/api/shots", {**SHOT, field: value})
                self._assert_invalid(status, body, field)
        for field in ("description", "camera", "lens_mm", "aperture", "framing"):
            with self.subTest(missing=field):
                shot = {k: v for k, v in SHOT.items() if k != field}
                status, body = self.harness.post("/api/shots", shot)
                self._assert_invalid(status, body, field)
        with self.subTest(body="not json"):
            status, body = self._raw_post(b"not json")
            self.assertEqual(status, 400)
            self.assertEqual(body["error"]["code"], "invalid_shot")
            self.assertTrue(body["error"]["message"])
        with self.subTest(body="array"):
            status, body = self._raw_post(b"[1, 2]")
            self.assertEqual(status, 400)
            self.assertEqual(body["error"]["code"], "invalid_shot")
            self.assertTrue(body["error"]["message"])
        self.assertEqual(self.harness.get("/api/shots"), (200, before))

    def test_missing_seed_gets_a_random_one(self):
        shot = {k: v for k, v in SHOT.items() if k != "seed"}
        status, record = self.harness.post("/api/shots", shot)
        self.assertEqual(status, 201, record)
        seed = record["params"]["seed"]
        self.assertIs(type(seed), int)
        self.assertTrue(0 <= seed <= 2147483647)
        self.assertIsInstance(record["derived"]["prompt"], str)
        self.assertTrue(record["derived"]["prompt"])
        self.assertAlmostEqual(record["derived"]["subject_distance_m"], 5.1005, places=3)
        self.assertEqual(record["status"], "queued")
        self.harness.wait_for_shot(record["id"], "done")


if __name__ == "__main__":
    unittest.main()
