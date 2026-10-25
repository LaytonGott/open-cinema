"""Check that ComfyUI has the nodes a graph needs before the app submits it."""

import asyncio
from urllib.parse import quote

import aiohttp


class ObjectInfoUnreachable(Exception):
    """ComfyUI's ``/object_info`` could not be read (no connection, timeout or HTTP 5xx)."""


def graph_class_types(*graphs):
    """Return the sorted list of distinct ``class_type`` values in the given graphs.

    Each graph is a dict ``id -> {"class_type", "inputs"}``.
    """
    found = set()
    for graph in graphs:
        for node in graph.values():
            found.add(node["class_type"])
    return sorted(found)


async def missing_nodes(comfyui_url, class_types):
    """Ask ComfyUI which of ``class_types`` it does not have.

    Does ``GET {comfyui_url}/object_info/<class_type>`` for each, concurrently,
    with a 5 second total timeout. Returns the sorted list of missing class
    types (a 404, or a 200 answer that is not a dict containing that class type).
    Raises ObjectInfoUnreachable on a connection error, a timeout or an HTTP 5xx.
    """
    base = comfyui_url.rstrip("/")
    timeout = aiohttp.ClientTimeout(total=5)

    async def is_missing(session, class_type):
        async with session.get(f"{base}/object_info/{quote(class_type, safe='')}") as resp:
            if resp.status == 404:
                return True
            if resp.status >= 500:
                raise ObjectInfoUnreachable(f"ComfyUI answered HTTP {resp.status}")
            if resp.status != 200:
                return True
            data = await resp.json(content_type=None)
            return not (isinstance(data, dict) and class_type in data)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            flags = await asyncio.gather(*(is_missing(session, c) for c in class_types))
    except ObjectInfoUnreachable:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as exc:
        raise ObjectInfoUnreachable(str(exc)) from exc
    return sorted(c for c, missing in zip(class_types, flags) if missing)


def nodes_missing_message(names):
    """Return the message telling the user which ComfyUI nodes are missing (names sorted, joined by ', ')."""
    return (f"ComfyUI is missing these nodes: {', '.join(sorted(names))}. "
            "Install the custom node pack that provides them and restart ComfyUI.")
