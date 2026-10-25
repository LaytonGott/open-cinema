"""ComfyUI health check for the director app."""

import asyncio

import aiohttp


async def check_health(comfyui_url):
    """Check whether ComfyUI answers ``GET {comfyui_url}/system_stats``.

    The request times out after 5 seconds in total, 1 second to connect.
    A refused, unreachable or timed-out connection, or a non-200 status, is
    not reachable. If the connection was made but the answer is too slow,
    ComfyUI is busy: reachable is True, ``device`` None and ``message``
    "ComfyUI is busy and answered slowly.".
    Returns the ``comfyui`` dict ``{"url", "reachable", "device", "message"}``:
    ``url`` is ``comfyui_url`` as given, ``device`` is the first device's name
    (or None), and ``message`` is None when reachable, else the error text.
    """
    result = {
        "url": comfyui_url,
        "reachable": False,
        "device": None,
        "message": f"Can't reach ComfyUI at {comfyui_url}. Start ComfyUI, then retry.",
    }
    timeout = aiohttp.ClientTimeout(total=5, sock_connect=1)
    connected = False

    async def on_connected(session, context, params):
        nonlocal connected
        connected = True

    trace = aiohttp.TraceConfig()
    trace.on_connection_create_end.append(on_connected)
    trace.on_connection_reuseconn.append(on_connected)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trace_configs=[trace]) as session:
            async with session.get(comfyui_url.rstrip("/") + "/system_stats") as resp:
                if resp.status != 200:
                    return result
                data = await resp.json(content_type=None)
    except (aiohttp.ClientConnectorError, OSError):
        return result
    except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
        if connected:
            result["reachable"] = True
            result["message"] = "ComfyUI is busy and answered slowly."
        return result
    except Exception:
        return result
    device = None
    try:
        device = data["devices"][0]["name"]
    except (KeyError, IndexError, TypeError):
        pass
    result["reachable"] = True
    result["device"] = device
    result["message"] = None
    return result
