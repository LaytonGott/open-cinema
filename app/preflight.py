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


async def _fetch_object_info(comfyui_url, class_types):
    """Fetch ``GET {comfyui_url}/object_info/<class_type>`` for each, concurrently (5 s total timeout).

    Returns a list parallel to ``class_types``: the decoded JSON answer of a 200,
    or None for a 404 or any other non-200 below 500. Raises ObjectInfoUnreachable
    on a connection error, a timeout or an HTTP 5xx.
    """
    base = comfyui_url.rstrip("/")
    timeout = aiohttp.ClientTimeout(total=5)

    async def fetch(session, class_type):
        async with session.get(f"{base}/object_info/{quote(class_type, safe='')}") as resp:
            if resp.status >= 500:
                raise ObjectInfoUnreachable(f"ComfyUI answered HTTP {resp.status}")
            if resp.status != 200:
                return None
            return await resp.json(content_type=None)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            return list(await asyncio.gather(*(fetch(session, c) for c in class_types)))
    except ObjectInfoUnreachable:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as exc:
        raise ObjectInfoUnreachable(str(exc)) from exc


async def missing_nodes(comfyui_url, class_types):
    """Ask ComfyUI which of ``class_types`` it does not have.

    Does ``GET {comfyui_url}/object_info/<class_type>`` for each, concurrently,
    with a 5 second total timeout. Returns the sorted list of missing class
    types (a 404, or a 200 answer that is not a dict containing that class type).
    Raises ObjectInfoUnreachable on a connection error, a timeout or an HTTP 5xx.
    """
    answers = await _fetch_object_info(comfyui_url, class_types)
    return sorted(c for c, data in zip(class_types, answers)
                  if not (isinstance(data, dict) and c in data))


async def missing_choices(comfyui_url, graphs):
    """Find combo choices in ``graphs`` that ComfyUI does not list.

    ``graphs`` is a list of graph dicts. Fetches ``/object_info/<class_type>``
    for every distinct class type (a 404 class is left out of the info), merges
    the answers into one object_info dict and returns the sorted list of unique
    ``(input_name, value, class_type)`` tuples from ``find_missing_choices`` over
    all graphs. Raises ObjectInfoUnreachable on a connection error, a timeout or
    an HTTP 5xx.
    """
    class_types = graph_class_types(*graphs)
    answers = await _fetch_object_info(comfyui_url, class_types)
    info = {}
    for data in answers:
        if isinstance(data, dict):
            info.update(data)
    found = set()
    for graph in graphs:
        found.update(find_missing_choices(graph, info))
    return sorted(found, key=lambda t: (t[0], str(t[1]), t[2]))


def nodes_missing_message(names):
    """Return the message telling the user which ComfyUI nodes are missing (names sorted, joined by ', ')."""
    return (f"ComfyUI is missing these nodes: {', '.join(sorted(names))}. "
            "Install the custom node pack that provides them and restart ComfyUI.")


def find_missing_choices(graph, object_info):
    """Find combo inputs whose value ComfyUI does not list as an option.

    ``graph`` is a dict ``id -> {"class_type", "inputs"}``; ``object_info`` is a
    dict ``class_type -> info`` with ``info["input"]["required"/"optional"]``.
    Link values (lists) are ignored, as are combos with no options, input
    ``file`` of LoadVideo and every combo input of SaveVideo. Returns a sorted
    list of unique ``(input_name, value, class_type)`` tuples.
    """
    found = set()
    for node in graph.values():
        class_type = node["class_type"]
        if class_type == "SaveVideo":
            continue
        groups = (object_info.get(class_type) or {}).get("input") or {}
        definitions = {}
        for group in ("required", "optional"):
            definitions.update(groups.get(group) or {})
        for name, value in node.get("inputs", {}).items():
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                continue
            if class_type == "LoadVideo" and name == "file":
                continue
            definition = definitions.get(name)
            if not isinstance(definition, (list, tuple)) or not definition:
                continue
            first = definition[0]
            if isinstance(first, list):
                options = first
            elif first == "COMBO" and len(definition) > 1 and isinstance(definition[1], dict):
                options = definition[1].get("options")
            else:
                continue
            if options and value not in options:
                found.add((name, value, class_type))
    return sorted(found, key=lambda t: (t[0], str(t[1]), t[2]))


def models_missing_message(items):
    """Return the message listing ``(name, value, class_type)`` choices ComfyUI does not list."""
    listed = ", ".join(f"{name} '{value}' ({class_type})" for name, value, class_type in items)
    return (f"ComfyUI does not list these files: {listed}. "
            "Put them in ComfyUI's models folders (see the README) and restart ComfyUI.")
