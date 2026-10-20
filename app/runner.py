"""Sequential shot runner: a queue of shot ids and one worker task."""
import asyncio
import logging
import time

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
