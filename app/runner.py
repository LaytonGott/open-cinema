"""Sequential shot runner: a queue of shot ids and one worker task."""
import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from app import comfy, graphs, progress

logger = logging.getLogger(__name__)


class ShotRunner:
    """Runs queued shots one at a time, in the order they were enqueued."""

    def __init__(self, store):
        self.store = store
        self.queue = None
        self.task = None
        self.client = None
        self._watchers = {}
        self.items = {}
        self.current = None
        self.cancel_requested = None

    def on_job_for(self, record):
        """Return the `on_job` callback for the shot `record` (called in a worker thread).

        The callback stores `{'shot_id', 'job'}` in `self.current` and cancels
        the job right away when `self.cancel_requested` is the shot's id.
        """
        def on_job(job):
            self.current = {"shot_id": record["id"], "job": job}
            if self.cancel_requested == record["id"]:
                job.cancel()
        return on_job

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

    def enqueue(self, shot_id, aperture=None):
        """Queue shot `shot_id`; the worker runs it after earlier items.

        `aperture` is None for a full run (`run_shot`) or an f-number for a
        re-apply (`run_reapply`). The item dict is kept in `self.items` until
        the worker finishes with it. Returns None.
        """
        item = {"shot_id": shot_id, "aperture": aperture,
                "cancelled": False, "started": False}
        self.items[shot_id] = item
        self.queue.put_nowait(item)

    def watch(self, shot_id):
        """Return a new asyncio.Event that `update` sets whenever it saves shot `shot_id`."""
        event = asyncio.Event()
        self._watchers.setdefault(shot_id, set()).add(event)
        return event

    def unwatch(self, shot_id, event):
        """Stop setting `event` (from `watch(shot_id)`) on updates; unknown events are ignored. Returns None."""
        events = self._watchers.get(shot_id)
        if events is None:
            return
        events.discard(event)
        if not events:
            del self._watchers[shot_id]

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
        for event in list(self._watchers.get(record["id"], ())):
            event.set()

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
        """Take items off the queue one at a time and run them. Never returns."""
        while True:
            item = await self.queue.get()
            shot_id = item["shot_id"]
            try:
                if item["cancelled"]:
                    continue
                item["started"] = True
                if item["aperture"] is None:
                    await self.run_shot(shot_id)
                else:
                    await self.run_reapply(shot_id, item["aperture"])
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
                if self.items.get(shot_id) is item:
                    del self.items[shot_id]
                self.queue.task_done()

    async def run_generation(self, record):
        """Generate the "before" video of the shot `record` in ComfyUI.

        Sets status 'generating' and the generate stage 'active', submits the
        generation graph, downloads its output to the shot folder as
        `before<ext>`, then sets `before_url`, the generate stage 'done'
        (progress 1.0) and the overall progress to at least 0.85. Errors
        propagate. Returns None.
        """
        shot_id = record["id"]
        self._set_stage(record, "generate", "active")
        self.update(record, status="generating", message="Waiting for ComfyUI")
        graph = graphs.build_generation_graph(
            record["derived"]["prompt"], record["params"]["seed"],
            f"opencinema/{shot_id}/before")
        loop = asyncio.get_running_loop()
        if self.client is None:
            self.client = comfy.make_client()
        try:
            job = await asyncio.to_thread(
                comfy.submit_and_follow, self.client, graph,
                self.thread_callback(loop, record, "generate"),
                self.on_job_for(record))
            path = await asyncio.to_thread(
                comfy.download_output, job, graphs.GENERATION_OUTPUT_NODE,
                self.store.shot_dir(shot_id), "before")
        finally:
            self.current = None
        self._set_stage(record, "generate", "done", 1.0)
        self.update(
            record,
            before_url=f"/media/{shot_id}/before{path.suffix}",
            progress=progress.monotonic(record.get("progress", 0.0), 0.85))

    def prepare_optics(self, record, aperture, n):
        """Upload the shot's "before" video and build its optics graph (blocking).

        `aperture` is the f-number and `n` the optics run number (the output
        prefix is `opencinema/<id>/after_<n>`). Creates the runner's client on
        first use. Returns `(client, graph)`.
        """
        shot_id = record["id"]
        if self.client is None:
            self.client = comfy.make_client()
        suffix = Path(record["before_url"]).suffix
        path = self.store.shot_dir(shot_id) / f"before{suffix}"
        uploaded = comfy.upload_video(self.client, path)
        graph = graphs.build_optics_graph(
            uploaded, record["params"]["lens_mm"], aperture,
            record["derived"]["subject_distance_m"],
            f"opencinema/{shot_id}/after_{n}")
        return self.client, graph

    @staticmethod
    def _set_stage(record, stage, state, stage_progress=None):
        for entry in record.get("stages") or []:
            if entry.get("id") == stage:
                entry["state"] = state
                if stage_progress is not None:
                    entry["progress"] = stage_progress

    def begin_reapply(self, record, aperture):
        """Mark the shot `record` as starting a re-apply at `aperture` (f-number).

        Sets `_reapply`, the generate stage 'done', the optics stage 'active'
        with progress 0.0, status 'optics', progress 0.0 and message
        'Estimating depth', and saves. Leaves `error` untouched. Returns None.
        """
        record["_reapply"] = True
        self._set_stage(record, "generate", "done")
        self._set_stage(record, "optics", "active", 0.0)
        self.update(record, status="optics", progress=0.0,
                    message="Estimating depth")

    def _finish_cancel(self, record):
        """Finish a cancelled shot `record` and save it. Returns None.

        Without versions the status becomes 'cancelled' with message
        'Cancelled.'. With versions (a cancelled re-apply) the shot goes back
        to status 'done', progress 1.0, message 'Done', `_reapply` is removed
        and the optics stage is 'done'.
        """
        if not record.get("versions"):
            self.update(record, status="cancelled", message="Cancelled.")
            return
        record.pop("_reapply", None)
        self._set_stage(record, "optics", "done")
        self.update(record, status="done", progress=1.0, message="Done")

    async def cancel(self, shot_id):
        """Cancel shot `shot_id`. Returns its record, or None if it is missing or not queued/generating/optics.

        A queued item that has not started is cancelled at once. Otherwise
        `cancel_requested` is set and the running job (if it is this shot's)
        is cancelled; the worker finishes the run.
        """
        record = self.store.get(shot_id)
        if record is None or record.get("status") not in ("queued", "generating", "optics"):
            return None
        item = self.items.get(shot_id)
        if item is not None and not item["started"]:
            item["cancelled"] = True
            self._finish_cancel(record)
            return record
        self.cancel_requested = shot_id
        current = self.current
        if current is not None and current["shot_id"] == shot_id:
            await asyncio.to_thread(current["job"].cancel)
        return record

    async def run_optics(self, record, aperture, n):
        """Apply the optics to the shot `record`'s "before" video as version `n`.

        `aperture` is the f-number. Sets status 'optics' and the optics stage
        'active', runs the optics graph in ComfyUI, downloads its output as
        `after_<n><ext>`, appends the version (`n`, `aperture`, `url`,
        `created_at` in UTC ISO ending in 'Z') to `versions`, sets
        `current_version`, the optics stage 'done', status 'done', progress
        1.0 and message 'Done'. Errors propagate. Returns None.
        """
        shot_id = record["id"]
        self._set_stage(record, "optics", "active")
        self.update(record, status="optics", message="Estimating depth")
        loop = asyncio.get_running_loop()
        client, graph = await asyncio.to_thread(
            self.prepare_optics, record, aperture, n)
        try:
            job = await asyncio.to_thread(
                comfy.submit_and_follow, client, graph,
                self.thread_callback(loop, record, "optics"),
                self.on_job_for(record))
            path = await asyncio.to_thread(
                comfy.download_output, job, graphs.OPTICS_OUTPUT_NODE,
                self.store.shot_dir(shot_id), f"after_{n}")
        finally:
            self.current = None
        created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        record.setdefault("versions", []).append({
            "n": n, "aperture": aperture,
            "url": f"/media/{shot_id}/after_{n}{path.suffix}",
            "created_at": created})
        self._set_stage(record, "optics", "done", 1.0)
        self.update(record, current_version=n, status="done", progress=1.0,
                    message="Done")

    async def run_reapply(self, shot_id, aperture):
        """Re-apply the optics to shot `shot_id` at `aperture` (f-number).

        Runs `run_optics` as the next version number (highest existing + 1,
        or 1 if none). Returns None.
        """
        record = self.store.get(shot_id)
        n = max((v["n"] for v in record.get("versions") or []), default=0) + 1
        await self.run_optics(record, aperture, n)

    async def run_shot(self, shot_id):
        """Run one shot: generate the video, then apply the optics as version 1."""
        record = self.store.get(shot_id)
        await self.run_generation(record)
        await self.run_optics(record, record["params"]["aperture"], 1)
