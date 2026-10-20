"""Sequential shot runner: a queue of shot ids and one worker task."""
import asyncio
import logging
import time

from app import progress

logger = logging.getLogger(__name__)


class ShotRunner:
    """Runs queued shots one at a time, in the order they were enqueued."""

    def __init__(self, store):
        self.store = store
        self.queue = None
        self.task = None

    def start(self):
        """Create the queue and the worker task; call inside a running loop."""
        self.queue = asyncio.Queue()
        self.task = asyncio.get_running_loop().create_task(self._worker())

    async def stop(self):
        """Cancel the worker task and wait for it (nothing is cancelled in ComfyUI)."""
        task, self.task = self.task, None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def enqueue(self, shot_id):
        """Put a shot id on the queue; the worker runs it after earlier ids."""
        self.queue.put_nowait(shot_id)

    def update(self, record, **changes):
        """Set `changes` on the shot `record`, refresh `elapsed_s` and save it.

        `elapsed_s` is the seconds since `record['_started']` (a
        `time.monotonic()` value, set now if missing), rounded to 1 decimal.
        Returns None.
        """
        record.update(changes)
        now = time.monotonic()
        started = record.setdefault("_started", now)
        record["elapsed_s"] = round(now - started, 1)
        self.store.save(record)

    def apply_event(self, record, stage, kind, data):
        """Apply one `submit_and_follow` event to the shot `record` (loop thread).

        `stage` is "generate" or "optics"; `kind` is "status" (`data` a str,
        only `elapsed_s` is refreshed) or "progress" (`data` a dict with
        `current_node`, `value` as a fraction 0 to 1, `step` and `steps`).
        Progress never falls: the stage and overall values keep the larger of
        old and new, and `message` comes from `message_for_node`. Returns None.
        """
        if kind != "progress":
            self.update(record)
            return
        fraction = max(0.0, min(1.0, data["value"]))
        if stage == "optics":
            overall = progress.optics_progress(fraction)
        else:
            overall = progress.generation_progress(fraction)
        stages = record.get("stages") or []
        for entry in stages:
            if entry.get("id") == stage:
                entry["progress"] = progress.monotonic(
                    entry.get("progress", 0.0), fraction)
        self.update(
            record,
            progress=progress.monotonic(record.get("progress", 0.0), overall),
            message=progress.message_for_node(
                stage, data["current_node"], data["step"], data["steps"]),
        )

    def thread_callback(self, loop, record, stage):
        """Return a function `(kind, data)` that, from any thread, schedules
        `apply_event(record, stage, kind, data)` on `loop`."""
        def callback(kind, data):
            loop.call_soon_threadsafe(self.apply_event, record, stage, kind, data)
        return callback

    async def _worker(self):
        while True:
            shot_id = await self.queue.get()
            try:
                await self.run_shot(shot_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("run_shot failed for shot %s", shot_id)
                record = self.store.get(shot_id)
                if record is not None:
                    self.update(record, status="failed", error={
                        "code": "internal",
                        "message": "Something went wrong inside Open Cinema. "
                                   "Check the console for details.",
                        "stage": "generate",
                    })
            finally:
                self.queue.task_done()

    async def run_shot(self, shot_id):
        """Run one shot; does nothing yet."""
