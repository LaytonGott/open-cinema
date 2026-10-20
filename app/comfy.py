"""The only app module that imports comfy_sdk: blocking helpers, call them in threads."""

from pathlib import Path

import comfy_sdk
from comfy_sdk import events


def make_client():
    """Return a comfy_sdk.Comfy client (it reads COMFY_BASE_URL, set by app.proxy)."""
    return comfy_sdk.Comfy()


def submit_and_follow(client, graph, on_event, on_job=None):
    """Submit graph, follow its events, wait for the result and return the job.

    Calls on_job(job) once if given, so a caller can cancel. Calls
    on_event('status', status_str) for each StatusChange and
    on_event('progress', d) for each Progress, where d is a dict with exactly the
    keys current_node, value, step and steps (current_node, step and steps may be
    None). Other event types are ignored. Exceptions propagate unchanged.
    """
    job = client.submit(client.workflows.from_json(graph))
    if on_job is not None:
        on_job(job)
    for ev in job.events():
        if isinstance(ev, events.StatusChange):
            on_event("status", ev.status)
        elif isinstance(ev, events.Progress):
            on_event("progress", {
                "current_node": ev.current_node,
                "value": ev.value,
                "step": ev.step,
                "steps": ev.steps,
            })
    job.result()
    return job


def upload_video(client, path):
    """Return client.assets.from_file(path), the Asset used as the LoadVideo `file` value."""
    return client.assets.from_file(path)


def download_output(job, node_id, dest_dir, stem):
    """Save the output of node_id from job into dest_dir as stem + extension; return the Path.

    The extension comes from the output's name ('.mp4' when it has none).
    Raises LookupError if job.outputs has no entry for node_id.
    """
    for output in job.outputs:
        if output.node_id == node_id:
            path = Path(dest_dir) / (stem + (Path(output.name).suffix or ".mp4"))
            output.to_file(path)
            return path
    raise LookupError(f"no output for node {node_id}")
