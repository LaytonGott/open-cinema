"""The only app module that imports comfy_sdk: blocking helpers, call them in threads."""

import os
from pathlib import Path

import comfy_sdk
from comfy_sdk import events

from app.outage import OutageGuard


def make_client():
    """Return a comfy_sdk.Comfy client (it reads COMFY_BASE_URL, set by app.proxy)."""
    return comfy_sdk.Comfy()


def submit_and_follow(client, graph, on_event, on_job=None, guard=None):
    """Submit graph, follow its events, wait for the result and return the job.

    Calls on_job(job) once if given, so a caller can cancel. Calls
    on_event('status', status_str) for each StatusChange and
    on_event('progress', d) for each Progress, where d is a dict with exactly the
    keys current_node, value, step, steps, nodes_total and nodes_done (current_node,
    step and steps may be None; nodes_total and nodes_done are 0 when the event has
    None). Other event types are ignored. Transient failures are retried through
    guard (default: a new OutageGuard); other exceptions propagate unchanged.
    """
    guard = guard or OutageGuard()
    job = guard.call(client.submit, client.workflows.from_json(graph))
    if on_job is not None:
        on_job(job)
    done = False
    while not done:
        stream = iter(job.events())
        while True:
            try:
                ev = next(stream)
            except StopIteration:
                done = True
                break
            except Exception as exc:
                guard.failed(exc)
                break
            guard.ok()
            if isinstance(ev, events.StatusChange):
                on_event("status", ev.status)
            elif isinstance(ev, events.Progress):
                on_event("progress", {
                    "current_node": None if ev.current_node is None else str(ev.current_node),
                    "value": ev.value,
                    "step": ev.step,
                    "steps": ev.steps,
                    "nodes_total": ev.nodes_total or 0,
                    "nodes_done": ev.nodes_done or 0,
                })
    guard.call(job.result)
    return job


def upload_video(client, path, guard=None):
    """Return client.assets.from_file(path), the Asset used as the LoadVideo `file` value.

    The upload runs through guard (default: a new OutageGuard), which retries transient errors.
    """
    guard = guard or OutageGuard()
    return guard.call(client.assets.from_file, path)


def download_output(job, node_id, dest_dir, stem, guard=None):
    """Save the output of node_id from job into dest_dir as stem + extension; return the Path.

    The extension comes from the output's name ('.mp4' when it has none).
    The download runs through guard (default: a new OutageGuard), which retries transient errors.
    It is written to '<name>.part' first and renamed to the final name only once complete, so the
    final file never exists half-written; on any failure the .part file is deleted.
    Raises LookupError if job.outputs has no entry for node_id.
    """
    guard = guard or OutageGuard()
    for output in job.outputs:
        if output.node_id == node_id:
            path = Path(dest_dir) / (stem + (Path(output.name).suffix or ".mp4"))
            part = path.with_name(path.name + ".part")
            try:
                guard.call(output.to_file, part)
                os.replace(part, path)
            except BaseException:
                try:
                    part.unlink()
                except OSError:
                    pass
                raise
            return path
    raise LookupError(f"no output for node {node_id}")
