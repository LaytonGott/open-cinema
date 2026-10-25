import asyncio
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from app.runner import ShotRunner
from app.store import ShotStore


def shot(shot_id):
    return {
        "id": shot_id, "status": "queued", "progress": 0.0, "message": "",
        "params": {"seed": 7, "lens_mm": 50, "aperture": 2.8},
        "derived": {"prompt": "a cat", "subject_distance_m": 3.0},
        "stages": [{"id": "generate", "state": "pending", "progress": 0.0},
                   {"id": "optics", "state": "pending", "progress": 0.0}]}


class RunnerSerialTest(unittest.TestCase):
    def test_second_job_waits_for_first_while_health_is_unreachable(self):
        lock = threading.Lock()
        release = threading.Event()
        state = {"active": 0, "max": 0, "calls": 0}
        events = []

        def fake_submit(client, graph, on_event, on_job=None, guard=None):
            with lock:
                state["active"] += 1
                state["calls"] += 1
                state["max"] = max(state["max"], state["active"])
                call = state["calls"]
                events.append(("start", call, time.monotonic()))
            try:
                if call == 1:
                    release.wait(10)
                else:
                    time.sleep(0.01)
            finally:
                with lock:
                    state["active"] -= 1
                    events.append(("end", call, time.monotonic()))
            return "job"

        def fake_download(job, node_id, dest_dir, stem):
            path = Path(dest_dir) / (stem + ".mp4")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x")
            return path

        async def unreachable(url):
            return {"url": url, "reachable": False, "device": None,
                    "message": "unreachable"}

        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            store.add(shot("s1"))
            store.add(shot("s2"))
            runner = ShotRunner(store)

            async def main():
                runner.start()
                runner.enqueue("s1")
                runner.enqueue("s2")
                deadline = time.monotonic() + 5
                while state["calls"] < 1 and time.monotonic() < deadline:
                    await asyncio.sleep(0.01)
                await asyncio.sleep(0.3)
                self.assertEqual(state["calls"], 1)
                release.set()
                deadline = time.monotonic() + 10
                while (store.get("s2")["status"] != "done"
                       and time.monotonic() < deadline):
                    await asyncio.sleep(0.01)
                await runner.stop()

            with mock.patch("app.comfy.make_client", lambda: "client"), \
                    mock.patch("app.comfy.upload_video", lambda c, p: "up.mp4"), \
                    mock.patch("app.comfy.submit_and_follow", fake_submit), \
                    mock.patch("app.comfy.download_output", fake_download), \
                    mock.patch("app.comfy_health.check_health", unreachable):
                asyncio.run(main())

            self.assertEqual(state["max"], 1)
            self.assertEqual(store.get("s1")["status"], "done")
            self.assertEqual(store.get("s2")["status"], "done")
            first_end = next(t for k, c, t in events if k == "end" and c == 1)
            second_start = next(t for k, c, t in events if k == "start" and c == 2)
            self.assertGreaterEqual(second_start, first_end)


if __name__ == "__main__":
    unittest.main()
