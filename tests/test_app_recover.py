import copy
import tempfile
import unittest

from app.store import ShotStore

STATUSES = ["queued", "generating", "optics", "done", "failed", "cancelled"]


class RecoverInterruptedTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        store = ShotStore(self.dir)
        self.saved = {}
        for status in STATUSES:
            record = {"id": f"shot_{status}", "status": status, "before_url": f"/media/{status}/before.png"}
            if status == "failed":
                record["error"] = {"code": "boom", "message": "It broke.", "stage": "generate"}
            store.add(record)
            self.saved[status] = copy.deepcopy(record)

    def recovered_store(self):
        store = ShotStore(self.dir)
        store.load_all()
        ids = store.recover_interrupted()
        return store, ids

    def check_store(self, store):
        for status in ("queued", "generating"):
            record = store.get(f"shot_{status}")
            self.assertEqual(record["status"], "failed")
            self.assertEqual(record["error"]["code"], "interrupted")
            self.assertEqual(record["error"]["stage"], "generate")
            self.assertTrue(record["error"]["message"])
            self.assertTrue(record["error"]["message"].endswith("."))
        optics = store.get("shot_optics")
        self.assertEqual(optics["status"], "failed")
        self.assertEqual(optics["error"]["code"], "interrupted")
        self.assertEqual(optics["error"]["stage"], "optics")
        self.assertEqual(optics["before_url"], self.saved["optics"]["before_url"])
        for status in ("done", "failed", "cancelled"):
            self.assertEqual(store.get(f"shot_{status}"), self.saved[status])
        self.assertEqual([r["id"] for r in store.list()], [f"shot_{s}" for s in STATUSES])

    def test_recover(self):
        store, ids = self.recovered_store()
        self.assertEqual(ids, ["shot_queued", "shot_generating", "shot_optics"])
        self.check_store(store)

    def test_persisted(self):
        self.recovered_store()
        again = ShotStore(self.dir)
        again.load_all()
        self.check_store(again)

    def test_second_call_returns_empty(self):
        store, _ = self.recovered_store()
        self.assertEqual(store.recover_interrupted(), [])
        self.check_store(store)


if __name__ == "__main__":
    unittest.main()
