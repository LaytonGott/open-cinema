import unittest

from app.record import new_record, public_record

PARAMS = {"description": "A woman walks.", "camera": "dolly-in", "lens_mm": 50,
          "aperture": 2.8, "framing": "full-body", "seed": 123}


class RecordTest(unittest.TestCase):
    def test_keys(self):
        r = new_record("abc", PARAMS)
        for key in ("id", "params", "derived", "status", "progress", "message",
                    "stages", "elapsed_s", "error", "reapply_error", "before_url",
                    "versions", "current_version"):
            self.assertIn(key, r)
        self.assertEqual(r["status"], "queued")
        self.assertEqual(r["message"], "Waiting for ComfyUI")
        self.assertEqual([s["id"] for s in r["stages"]], ["generate", "optics"])
        self.assertEqual(r["versions"], [])
        self.assertIsNone(r["current_version"])
        self.assertIn("prompt", r["derived"])

    def test_distance(self):
        r = new_record("abc", PARAMS)
        self.assertAlmostEqual(r["derived"]["subject_distance_m"], 5.1005, places=3)

    def test_public_record_drops_internal(self):
        r = new_record("abc", PARAMS)
        r["seq"] = 3
        r["_task"] = object()
        p = public_record(r)
        self.assertNotIn("seq", p)
        self.assertNotIn("_task", p)
        self.assertEqual(p["id"], "abc")
        self.assertIn("seq", r)


if __name__ == "__main__":
    unittest.main()
