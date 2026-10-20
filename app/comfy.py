"""The only app module that imports comfy_sdk: blocking helpers, call them in threads."""

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
    job = client.submit(graph)
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
