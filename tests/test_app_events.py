import json
import time
import unittest
import urllib.error
import urllib.request

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


def read_frames(harness, shot_id, stamps=None):
    """Read the events stream to its end; return the list of `shot` records (and stamp each in `stamps`)."""
    frames = []
    event = None
    with urllib.request.urlopen(harness.url + f"/api/shots/{shot_id}/events", timeout=30) as resp:
        while True:
            line = resp.readline()
            if line == b"":
                break
            text = line.decode("utf-8").rstrip("\r\n")
            if text.startswith("event:"):
                event = text[6:].strip()
            elif text.startswith("data:") and event == "shot":
                frames.append(json.loads(text[5:].strip()))
                if stamps is not None:
                    stamps.append(time.monotonic())
    return frames


class EventsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.fake.start()
        cls.harness = AppHarness(fake=cls.fake)
        cls.harness.start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.stop()

    def submit(self, **extra):
        status, body = self.harness.post("/api/shots", dict(SHOT, **extra))
        self.assertEqual(status, 201)
        return body["id"]

    def test_held_shot_streams_to_done(self):
        self.fake.hold_at("SamplerCustomAdvanced")
        try:
            shot_id = self.submit(seed=11)
            self.harness.wait_until(shot_id, lambda r: r["status"] in ("generating", "optics"), what="shot busy")
            with urllib.request.urlopen(self.harness.url + f"/api/shots/{shot_id}/events", timeout=30) as resp:
                first = None
                frames = []
                event = None
                released = False
                while True:
                    line = resp.readline()
                    if line == b"":
                        break
                    text = line.decode("utf-8").rstrip("\r\n")
                    if text.startswith("event:"):
                        event = text[6:].strip()
                    elif text.startswith("data:") and event == "shot":
                        frames.append(json.loads(text[5:].strip()))
                        if not released:
                            first = frames[0]
                            self.fake.release()
                            released = True
                self.assertIsNotNone(first)
                self.assertIn(first["status"], ("queued", "generating"))
                self.assertEqual(frames[-1]["status"], "done")
                progress = [f["progress"] for f in frames]
                self.assertEqual(progress, sorted(progress))
        finally:
            self.fake.release()

    def test_finished_shot_gives_one_frame(self):
        shot_id = self.submit(seed=12)
        self.harness.wait_for_shot(shot_id)
        frames = read_frames(self.harness, shot_id)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["status"], "done")

    def test_unknown_id_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.harness.url + "/api/shots/nope/events", timeout=30)
        self.assertEqual(ctx.exception.code, 404)
        body = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(body["error"]["code"], "not_found")

    def test_frame_rate_is_limited(self):
        shot_id = self.submit(seed=13)
        stamps = []
        frames = read_frames(self.harness, shot_id, stamps)
        self.assertEqual(frames[-1]["status"], "done")
        self.assertLess(len(frames), 40)
        for i, start in enumerate(stamps):
            in_window = [s for s in stamps[i:] if s - start < 1.0]
            self.assertLessEqual(len(in_window), 6)


if __name__ == "__main__":
    unittest.main()
