import json
import unittest
import urllib.error
import urllib.request

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy

EVIL = "http://evil.example"


def raw(url, method="GET", body=None, headers=None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class OriginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def _shot_ids(self):
        status, body = self.harness.get("/api/shots")
        self.assertEqual(status, 200)
        shots = body["shots"] if isinstance(body, dict) else body
        return [s["id"] for s in shots]

    def _call(self, path, method, payload, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        return raw(self.harness.url + path, method, json.dumps(payload).encode(), headers)

    def _assert_forbidden(self, status, body):
        self.assertEqual(status, 403)
        err = json.loads(body)["error"]
        self.assertEqual(err["code"], "forbidden_origin")
        self.assertEqual(err["message"], "Requests from other sites are not allowed.")
        self.assertIsNone(err["field"])

    def test_foreign_origin_refused_and_own_allowed(self):
        h = self.harness
        h.reset()
        before = self._shot_ids()
        self._assert_forbidden(*self._call("/api/shots", "POST", SHOT, EVIL))
        self.assertEqual(self._shot_ids(), before)

        status, body = self._call("/api/shots", "POST", SHOT)
        self.assertEqual(status, 201)
        sid = json.loads(body)["id"]
        h.wait_for_shot(sid, "done")

        status, _ = self._call(f"/api/shots/{sid}/reapply", "POST", {"aperture": 8}, f"http://127.0.0.1:{h.port}")
        self.assertEqual(status, 202)
        h.wait_for_shot(sid, "done")

        self._assert_forbidden(*self._call(f"/api/shots/{sid}/reapply", "POST", {"aperture": 8}, EVIL))
        self._assert_forbidden(*self._call(f"/api/shots/{sid}", "DELETE", {}, EVIL))
        self.assertIn(sid, self._shot_ids())
        self._assert_forbidden(*self._call("/api/shots/import", "POST", {"x": 1}, EVIL))

    def test_get_with_foreign_origin_not_refused(self):
        status, _ = raw(self.harness.url + "/api/shots", "GET", None, {"Origin": EVIL})
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
